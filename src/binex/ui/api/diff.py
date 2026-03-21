"""Diff API endpoint for Binex Web UI.

Delegates to trace.diff.diff_runs() and reshapes the result
to match the Web UI API contract.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.cli import get_stores
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.trace.diff import diff_runs as core_diff_runs

router = APIRouter(prefix="/diff", tags=["diff"])


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


class DiffRequest(BaseModel):
    """Request body for comparing two runs."""

    run_a: str
    run_b: str


def _reshape_for_frontend(result: dict[str, Any], run_id_a: str, run_id_b: str) -> dict[str, Any]:
    """Transform core diff_runs() result into the frontend API contract."""
    records_a_count = sum(1 for s in result["steps"] if s["status_a"] is not None)
    records_b_count = sum(1 for s in result["steps"] if s["status_b"] is not None)

    total_cost_a = sum(s.get("cost_a", 0.0) for s in result["steps"])
    total_cost_b = sum(s.get("cost_b", 0.0) for s in result["steps"])

    node_diffs = [
        {
            "node_id": step["task_id"],
            "status_a": step["status_a"],
            "status_b": step["status_b"],
            "duration_a": step["latency_a"],
            "duration_b": step["latency_b"],
            "cost_a": step.get("cost_a", 0.0),
            "cost_b": step.get("cost_b", 0.0),
            "artifact_diff": step.get("artifact_diff"),
        }
        for step in result["steps"]
    ]

    return {
        "run_a": {
            "run_id": run_id_a,
            "status": result["status_a"],
            "total_cost": total_cost_a,
            "node_count": records_a_count,
        },
        "run_b": {
            "run_id": run_id_b,
            "status": result["status_b"],
            "total_cost": total_cost_b,
            "node_count": records_b_count,
        },
        "node_diffs": node_diffs,
    }


@router.post("")
async def diff_runs(body: DiffRequest) -> JSONResponse:
    """Compare two runs node-by-node."""
    exec_store, art_store = _get_stores()
    try:
        try:
            result = await core_diff_runs(exec_store, art_store, body.run_a, body.run_b)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)

        return JSONResponse(_reshape_for_frontend(result, body.run_a, body.run_b))
    finally:
        await exec_store.close()
