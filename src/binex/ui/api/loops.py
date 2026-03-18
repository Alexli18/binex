"""Loops API endpoints — iteration data for loop container nodes."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.cli import get_stores

router = APIRouter(prefix="/loops", tags=["loops"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/{run_id}")
async def get_loops(run_id: str) -> JSONResponse:
    """Get loop iteration data for a workflow run."""
    exec_store, artifact_store = _get_stores()

    try:
        records = await exec_store.list_records(run_id)

        # Filter records with iteration_number (these are loop inner nodes)
        loop_records = [r for r in records if r.iteration_number is not None]

        if not loop_records:
            return JSONResponse({"run_id": run_id, "loops": []})

        # Fetch costs once (not per-record)
        cost_records = await exec_store.list_costs(run_id)
        cost_by_task: dict[str, float] = defaultdict(float)
        for c in cost_records:
            cost_by_task[c.task_id] += c.cost

        # Group by loop_node_id (extracted from task_id pattern: loop_id.node_id)
        loops: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
        for rec in loop_records:
            parts = rec.task_id.split(".", 1)
            if len(parts) == 2:
                loop_id, inner_node = parts
            else:
                loop_id = rec.task_id
                inner_node = rec.task_id

            loops[loop_id][rec.iteration_number].append({
                "node_id": inner_node,
                "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
                "latency_ms": rec.latency_ms,
                "cost": cost_by_task.get(rec.task_id, 0.0),
                "error": rec.error,
            })

        # Build response
        result_loops = []
        for loop_id, iterations in loops.items():
            iter_list = []
            for iter_num in sorted(iterations.keys()):
                nodes = iterations[iter_num]
                all_completed = all(n["status"] == "completed" for n in nodes)
                iter_list.append({
                    "iteration": iter_num,
                    "status": "completed" if all_completed else "failed",
                    "nodes": nodes,
                })

            result_loops.append({
                "loop_node_id": loop_id,
                "iterations": iter_list,
                "total_iterations": len(iter_list),
            })

        return JSONResponse({"run_id": run_id, "loops": result_loops})
    finally:
        await exec_store.close()


@router.get("/{run_id}/{loop_node_id}")
async def get_loop_detail(run_id: str, loop_node_id: str) -> JSONResponse:
    """Get detailed iteration data for a specific loop node."""
    exec_store, artifact_store = _get_stores()

    try:
        records = await exec_store.list_records(run_id)
        loop_records = [
            r for r in records
            if r.iteration_number is not None
            and r.task_id.startswith(f"{loop_node_id}.")
        ]

        if not loop_records:
            return JSONResponse({
                "run_id": run_id,
                "loop_node_id": loop_node_id,
                "iterations": [],
                "total_iterations": 0,
            })

        iterations: dict[int, list] = defaultdict(list)
        cost_records = await exec_store.list_costs(run_id)
        cost_by_task: dict[str, float] = defaultdict(float)
        for c in cost_records:
            cost_by_task[c.task_id] += c.cost

        for rec in loop_records:
            inner_node = rec.task_id.split(".", 1)[1] if "." in rec.task_id else rec.task_id

            iterations[rec.iteration_number].append({
                "node_id": inner_node,
                "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
                "latency_ms": rec.latency_ms,
                "cost": cost_by_task.get(rec.task_id, 0.0),
                "error": rec.error,
                "output_artifact_refs": rec.output_artifact_refs,
            })

        iter_list = []
        for iter_num in sorted(iterations.keys()):
            nodes = iterations[iter_num]
            all_completed = all(n["status"] == "completed" for n in nodes)
            iter_list.append({
                "iteration": iter_num,
                "status": "completed" if all_completed else "failed",
                "nodes": nodes,
            })

        return JSONResponse({
            "run_id": run_id,
            "loop_node_id": loop_node_id,
            "iterations": iter_list,
            "total_iterations": len(iter_list),
        })
    finally:
        await exec_store.close()
