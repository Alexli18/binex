"""Diagnose API endpoint for Binex Web UI."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.cli import get_stores
from binex.trace.diagnose import diagnose_run, report_to_dict

router = APIRouter(prefix="/runs", tags=["diagnose"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/{run_id}/diagnose")
async def get_diagnose(run_id: str) -> JSONResponse:
    """Root-cause analysis for a workflow run."""
    exec_store, art_store = _get_stores()
    try:
        run = await exec_store.get_run(run_id)
        if run is None:
            return JSONResponse(
                {"error": f"Run '{run_id}' not found"}, status_code=404,
            )

        report = await diagnose_run(exec_store, art_store, run_id)
        result = report_to_dict(report)

        # Add severity based on status and issues
        if report.root_cause:
            severity = "HIGH"
        elif report.latency_anomalies:
            severity = "MEDIUM"
        elif report.status == "issues_found":
            severity = "LOW"
        else:
            severity = "NONE"

        # Add total cost from run summary
        result["severity"] = severity
        result["total_cost"] = run.total_cost

        # Reshape root_causes as a list for the API
        root_causes = []
        if report.root_cause:
            root_causes.append({
                "node_id": report.root_cause.node_id,
                "error": report.root_cause.error_message,
                "status": "failed",
            })
        result["root_causes"] = root_causes

        return JSONResponse(result)
    finally:
        await exec_store.close()
