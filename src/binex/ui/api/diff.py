"""Diff API endpoint for Binex Web UI."""

from __future__ import annotations

import difflib

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.cli import get_stores

router = APIRouter(prefix="/diff", tags=["diff"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


class DiffRequest(BaseModel):
    """Request body for comparing two runs."""

    run_a: str
    run_b: str


async def _get_artifact_text(art_store, refs: list[str]) -> str:
    """Concatenate artifact contents from a list of refs into a single string."""
    parts: list[str] = []
    for ref in refs:
        art = await art_store.get(ref)
        if art is not None and art.content is not None:
            parts.append(str(art.content))
    return "\n".join(parts)


@router.post("")
async def diff_runs(body: DiffRequest) -> JSONResponse:
    """Compare two runs node-by-node."""
    exec_store, art_store = _get_stores()
    try:
        run_a = await exec_store.get_run(body.run_a)
        if run_a is None:
            return JSONResponse(
                {"error": f"Run '{body.run_a}' not found"}, status_code=404,
            )

        run_b = await exec_store.get_run(body.run_b)
        if run_b is None:
            return JSONResponse(
                {"error": f"Run '{body.run_b}' not found"}, status_code=404,
            )

        records_a = await exec_store.list_records(body.run_a)
        records_b = await exec_store.list_records(body.run_b)

        by_task_a = {r.task_id: r for r in records_a}
        by_task_b = {r.task_id: r for r in records_b}

        all_tasks = sorted(set(by_task_a.keys()) | set(by_task_b.keys()))

        # Build cost lookup
        costs_a_list = await exec_store.list_costs(body.run_a)
        costs_b_list = await exec_store.list_costs(body.run_b)
        cost_by_task_a: dict[str, float] = {}
        for c in costs_a_list:
            cost_by_task_a[c.task_id] = cost_by_task_a.get(c.task_id, 0.0) + c.cost
        cost_by_task_b: dict[str, float] = {}
        for c in costs_b_list:
            cost_by_task_b[c.task_id] = cost_by_task_b.get(c.task_id, 0.0) + c.cost

        total_cost_a = sum(cost_by_task_a.values())
        total_cost_b = sum(cost_by_task_b.values())

        node_diffs: list[dict] = []
        for task_id in all_tasks:
            rec_a = by_task_a.get(task_id)
            rec_b = by_task_b.get(task_id)

            status_a = rec_a.status.value if rec_a else None
            status_b = rec_b.status.value if rec_b else None
            duration_a = rec_a.latency_ms if rec_a else None
            duration_b = rec_b.latency_ms if rec_b else None

            refs_a = rec_a.output_artifact_refs if rec_a else []
            refs_b = rec_b.output_artifact_refs if rec_b else []

            content_a = await _get_artifact_text(art_store, refs_a)
            content_b = await _get_artifact_text(art_store, refs_b)

            artifact_diff = None
            if content_a != content_b:
                diff_lines = list(difflib.unified_diff(
                    content_a.splitlines(keepends=True),
                    content_b.splitlines(keepends=True),
                    fromfile=f"{body.run_a}/{task_id}",
                    tofile=f"{body.run_b}/{task_id}",
                ))
                artifact_diff = "".join(diff_lines) if diff_lines else None

            node_diffs.append({
                "node_id": task_id,
                "status_a": status_a,
                "status_b": status_b,
                "duration_a": duration_a,
                "duration_b": duration_b,
                "cost_a": cost_by_task_a.get(task_id, 0.0),
                "cost_b": cost_by_task_b.get(task_id, 0.0),
                "artifact_diff": artifact_diff,
            })

        return JSONResponse({
            "run_a": {
                "run_id": body.run_a,
                "status": run_a.status,
                "total_cost": total_cost_a,
                "node_count": len(records_a),
            },
            "run_b": {
                "run_id": body.run_b,
                "status": run_b.status,
                "total_cost": total_cost_b,
                "node_count": len(records_b),
            },
            "node_diffs": node_diffs,
        })
    finally:
        await exec_store.close()
