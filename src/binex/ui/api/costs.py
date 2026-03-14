"""Costs API endpoints for Binex Web UI."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.cli import get_stores

router = APIRouter(prefix="/runs", tags=["costs"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/{run_id}/costs")
async def get_costs(run_id: str) -> JSONResponse:
    """Get cost breakdown for a workflow run."""
    exec_store, _ = _get_stores()
    summary = await exec_store.get_run_cost_summary(run_id)
    records = await exec_store.list_costs(run_id)
    return JSONResponse({
        "run_id": run_id,
        "total_cost": summary.total_cost,
        "records": [
            {
                "run_id": r.run_id,
                "node_id": r.task_id,
                "cost": r.cost,
                "model": r.model,
                "source": r.source,
            }
            for r in records
        ],
    })
