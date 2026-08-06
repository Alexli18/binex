"""Eval REST API endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from binex.cli import get_stores

router = APIRouter(prefix="/eval", tags=["eval"])


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/executions")
async def list_eval_executions(
    limit: int = Query(default=50, ge=1, le=500),
    suite: str | None = Query(default=None),
) -> dict:
    """List recent eval suite executions (newest first)."""
    exec_store, _ = _get_stores()
    try:
        rows = await exec_store.list_eval_results(limit=limit, suite_name=suite)
    finally:
        await exec_store.close()

    executions = []
    for row in rows:
        try:
            payload = json.loads(row.get("payload", "{}"))
        except (json.JSONDecodeError, AttributeError):
            payload = {}
        executions.append({
            "id": row.get("id"),
            "suite_name": row.get("suite_name"),
            "executed_at": row.get("executed_at"),
            "total": payload.get("total", 0),
            "passed": payload.get("passed", 0),
            "failed": payload.get("failed", 0),
            "no_baseline": payload.get("no_baseline", 0),
            "total_cost": payload.get("total_cost", 0.0),
        })
    return {"executions": executions}


@router.get("/executions/{result_id}")
async def get_eval_execution(result_id: str) -> dict:
    """Get full EvalResult payload for a specific execution."""
    exec_store, _ = _get_stores()
    try:
        row = await exec_store.get_eval_result(result_id)
    finally:
        await exec_store.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Eval result '{result_id}' not found")

    try:
        payload = json.loads(row.get("payload", "{}"))
    except (json.JSONDecodeError, AttributeError):
        payload = {}

    return {
        "id": row.get("id"),
        "suite_name": row.get("suite_name"),
        **payload,
    }


@router.get("/baselines")
async def get_eval_baselines(suite: str = Query(...)) -> dict:
    """Get current baselines for all cases in the named suite."""
    exec_store, _ = _get_stores()
    try:
        baselines = await exec_store.get_baselines(suite)
    finally:
        await exec_store.close()

    return {
        "suite": suite,
        "baselines": [
            {"case_id": case_id, "run_id": run_id}
            for case_id, run_id in baselines.items()
        ],
    }
