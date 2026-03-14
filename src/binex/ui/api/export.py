"""Export API endpoint for Binex Web UI."""

from __future__ import annotations

import csv
import io
import json
import zipfile

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from binex.cli import get_stores

router = APIRouter(prefix="/export", tags=["export"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


class ExportRequest(BaseModel):
    """Request body for data export."""

    run_ids: list[str]
    format: str = "json"  # "json" or "csv"
    include_artifacts: bool = False


def _runs_to_dicts(runs) -> list[dict]:
    """Convert RunSummary list to serializable dicts."""
    return [r.model_dump(mode="json") for r in runs]


def _records_to_dicts(records) -> list[dict]:
    """Convert ExecutionRecord list to serializable dicts."""
    return [r.model_dump(mode="json") for r in records]


def _costs_to_dicts(costs) -> list[dict]:
    """Convert CostRecord list to serializable dicts."""
    return [r.model_dump(mode="json") for r in costs]


def _write_csv(rows: list[dict]) -> str:
    """Write a list of dicts to CSV string."""
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


@router.post("", response_model=None)
async def export_data(body: ExportRequest) -> StreamingResponse | JSONResponse:
    """Export run data as JSON or CSV (zip)."""
    if not body.run_ids:
        return JSONResponse({"error": "run_ids must not be empty"}, status_code=422)

    if body.format not in ("json", "csv"):
        return JSONResponse(
            {"error": f"Unsupported format: {body.format}"},
            status_code=422,
        )

    exec_store, artifact_store = _get_stores()
    try:
        runs = []
        all_records = []
        all_costs = []
        not_found = []

        for run_id in body.run_ids:
            run = await exec_store.get_run(run_id)
            if run is None:
                not_found.append(run_id)
                continue
            runs.append(run)
            records = await exec_store.list_records(run_id)
            costs = await exec_store.list_costs(run_id)
            all_records.extend(records)
            all_costs.extend(costs)

        if not runs:
            return JSONResponse(
                {"error": f"No runs found: {', '.join(not_found)}"},
                status_code=404,
            )

        # Gather artifacts if requested
        artifacts = None
        if body.include_artifacts:
            artifacts = []
            for run in runs:
                arts = await artifact_store.list_by_run(run.run_id)
                artifacts.extend(arts)

        if body.format == "json":
            data: dict = {
                "runs": _runs_to_dicts(runs),
                "records": _records_to_dicts(all_records),
                "costs": _costs_to_dicts(all_costs),
            }
            if artifacts is not None:
                data["artifacts"] = [a.model_dump(mode="json") for a in artifacts]

            content = json.dumps(data, default=str, indent=2)
            return StreamingResponse(
                iter([content]),
                media_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=binex-export.json",
                },
            )

        # CSV format — zip with multiple files
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("runs.csv", _write_csv(_runs_to_dicts(runs)))
            zf.writestr("records.csv", _write_csv(_records_to_dicts(all_records)))
            zf.writestr("costs.csv", _write_csv(_costs_to_dicts(all_costs)))
            if artifacts is not None:
                zf.writestr(
                    "artifacts.json",
                    json.dumps(
                        [a.model_dump(mode="json") for a in artifacts],
                        default=str, indent=2,
                    ),
                )

        zip_buf.seek(0)
        return StreamingResponse(
            iter([zip_buf.getvalue()]),
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=binex-export.zip",
            },
        )
    finally:
        await exec_store.close()
