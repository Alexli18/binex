"""Bisect API endpoint for Binex Web UI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from binex.cli import get_stores
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore

router = APIRouter(prefix="/bisect", tags=["bisect"])


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _field_changes(nc: Any | None) -> list[dict[str, Any]] | None:
    """Serialize a node's per-field differences.

    None means the outputs were compared as text and there is no per-field
    detail; an empty list means structured content that is identical.
    """
    from dataclasses import asdict

    if nc is None or nc.field_changes is None:
        return None
    return [asdict(c) for c in nc.field_changes]


class BisectRequest(BaseModel):
    """Request body for bisecting two runs."""

    good_run: str
    bad_run: str
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    # Opt-in: a judge decides text nodes instead of `threshold`, and it spends
    # the caller's tokens. The UI is expected to show /bisect/estimate first and
    # get an explicit confirmation — the browser must not be a way around the
    # cost prompt the CLI enforces.
    semantic: bool = False
    semantic_model: str | None = None


class EstimateRequest(BaseModel):
    """Request body for a pre-flight semantic-analysis cost estimate."""

    good_run: str
    bad_run: str
    semantic_model: str | None = None


def _estimate_payload(pairs: list[tuple[str, str, str]], model: str) -> dict[str, Any]:
    """Shape a CostEstimate for the API, shared by the bisect and diff routes."""
    from binex.trace.semantic_judge import estimate_cost

    est = estimate_cost(pairs, model)
    return {
        "calls": est.calls,
        "prompt_tokens": est.prompt_tokens,
        "completion_tokens": est.completion_tokens,
        "total_tokens": est.total_tokens,
        # None when the model has no published pricing — render as "unknown".
        "cost": est.cost,
        "model": model,
        "nodes": [node_id for node_id, _a, _b in pairs],
    }


@router.post("/estimate")
async def estimate_semantic(body: EstimateRequest) -> JSONResponse:
    """How much a semantic bisect of these two runs would cost.

    An upper bound: the walk stops at the first meaningful divergence, so fewer
    calls than quoted is the normal case. Structured content is absent from the
    count — it is compared field-wise, exactly and for free.
    """
    from binex.eval.judge import resolve_judge_model
    from binex.trace.bisect import semantic_candidates

    exec_store, art_store = _get_stores()
    try:
        try:
            pairs = await semantic_candidates(
                exec_store, art_store, body.good_run, body.bad_run,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)
        model = resolve_judge_model(body.semantic_model)
        return JSONResponse(_estimate_payload(pairs, model))
    finally:
        await exec_store.close()


@router.post("")
async def bisect_runs(body: BisectRequest) -> JSONResponse:
    """Find the first node where two runs diverge."""
    from binex.runtime.replay import ImportedRunError, ensure_replayable

    exec_store, art_store = _get_stores()
    try:
        # Feature gate: neither run may be an imported run
        for run_id in (body.good_run, body.bad_run):
            run = await exec_store.get_run(run_id)
            if run is not None:
                try:
                    ensure_replayable(run, operation="bisect")
                except ImportedRunError as e:
                    return JSONResponse({"error": str(e)}, status_code=422)

        from binex.trace.bisect import bisect_report

        judge = None
        if body.semantic:
            from binex.eval.judge import resolve_judge_model
            from binex.trace.semantic_judge import make_semantic_judge

            judge = make_semantic_judge(resolve_judge_model(body.semantic_model))

        try:
            report = await bisect_report(
                exec_store, art_store,
                body.good_run, body.bad_run, body.threshold,
                semantic_judge=judge,
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=404)

        # Reshape to match the API contract
        dp = report.divergence_point
        response: dict[str, Any] = {
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
                "field_changes": _field_changes(nc_match),
                "semantic_reason": dp.semantic_reason,
            }

        # Add node_map for full per-node comparison data
        response["node_map"] = [
            {
                "node_id": nc.node_id,
                "status": nc.status,
                "good_status": nc.good_status,
                "bad_status": nc.bad_status,
                "similarity": nc.similarity,
                "latency_good_ms": nc.latency_good_ms,
                "latency_bad_ms": nc.latency_bad_ms,
                "field_changes": _field_changes(nc),
                "semantic_verdict": nc.semantic_verdict,
            }
            for nc in report.node_map
        ]

        # Add downstream impact list
        response["downstream_impact"] = report.downstream_impact

        return JSONResponse(response)
    finally:
        await exec_store.close()
