"""Bisect API endpoint for Binex Web UI."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from binex.cli import get_stores

router = APIRouter(prefix="/bisect", tags=["bisect"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


class BisectRequest(BaseModel):
    """Request body for bisecting two runs."""

    good_run: str
    bad_run: str
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)


@router.post("")
async def bisect_runs(body: BisectRequest) -> JSONResponse:
    """Find the first node where two runs diverge."""
    exec_store, art_store = _get_stores()
    try:
        from binex.trace.bisect import bisect_report

        try:
            report = await bisect_report(
                exec_store, art_store,
                body.good_run, body.bad_run, body.threshold,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)

        # Reshape to match the API contract
        dp = report.divergence_point
        response: dict = {
            "good_run": body.good_run,
            "bad_run": body.bad_run,
            "divergence_node": dp.node_id if dp else None,
            "divergence_index": None,
            "similarity": dp.similarity if dp else None,
            "details": None,
        }

        # Find divergence index
        if dp is not None:
            for i, nc in enumerate(report.node_map):
                if nc.node_id == dp.node_id:
                    response["divergence_index"] = i
                    break

            # Build details from divergence point and node comparison
            nc_match = next(
                (nc for nc in report.node_map if nc.node_id == dp.node_id),
                None,
            )
            diff_text = None
            if nc_match and nc_match.content_diff:
                diff_text = "\n".join(nc_match.content_diff)

            response["details"] = {
                "node_id": dp.node_id,
                "good_status": dp.good_status,
                "bad_status": dp.bad_status,
                "good_output": None,
                "bad_output": None,
                "diff": diff_text,
            }

        return JSONResponse(response)
    finally:
        await exec_store.close()
