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
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore
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
    # Opt-in: asks a judge whether each changed text node changed *meaningfully*,
    # and spends the caller's tokens doing it. The UI shows /diff/estimate first
    # and gets an explicit confirmation — the browser must not bypass the cost
    # prompt the CLI enforces.
    semantic: bool = False
    semantic_model: str | None = None


class DiffEstimateRequest(BaseModel):
    """Request body for a pre-flight semantic-analysis cost estimate."""

    run_a: str
    run_b: str
    semantic_model: str | None = None


@router.post("/estimate")
async def estimate_semantic(body: DiffEstimateRequest) -> JSONResponse:
    """How much a semantic diff of these two runs would cost.

    Only nodes whose text content actually differs are counted: identical
    outputs and structured content are settled without a model.
    """
    from binex.eval.judge import resolve_judge_model
    from binex.trace.diff import diff_runs as core_diff_runs
    from binex.trace.semantic_diff import changed_pairs
    from binex.ui.api.bisect import _estimate_payload

    exec_store, art_store = _get_stores()
    try:
        try:
            result = await core_diff_runs(
                exec_store, art_store, body.run_a, body.run_b,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        model = resolve_judge_model(body.semantic_model)
        return JSONResponse(_estimate_payload(changed_pairs(result), model))
    finally:
        await exec_store.close()


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
            "content_similarity": step.get("content_similarity"),
            # None for text content (no per-field detail), [] when structured
            # content is identical, one rendered line per changed field otherwise.
            "field_changes": step.get("field_changes"),
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

        payload = _reshape_for_frontend(result, body.run_a, body.run_b)

        if body.semantic:
            from binex.eval.judge import resolve_judge_model
            from binex.trace.semantic_diff import analyze_diff, verdicts_to_json
            from binex.trace.semantic_judge import make_semantic_judge

            judge = make_semantic_judge(resolve_judge_model(body.semantic_model))
            payload["semantic"] = verdicts_to_json(await analyze_diff(result, judge))

        return JSONResponse(payload)
    finally:
        await exec_store.close()
