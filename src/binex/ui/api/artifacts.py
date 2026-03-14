"""Artifacts API endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from binex.cli import get_stores

router = APIRouter()


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/runs/{run_id}/artifacts")
async def get_artifacts(run_id: str) -> dict[str, Any]:
    """Return all artifacts for a given run."""
    _, art_store = _get_stores()
    artifacts = await art_store.list_by_run(run_id)
    result = []
    for art in artifacts:
        derived = art.lineage.derived_from if art.lineage.derived_from else None
        result.append({
            "type": art.type,
            "content": art.content,
            "lineage": {
                "produced_by": art.lineage.produced_by,
                "step": 0,
                "derived_from": derived,
            },
        })
    return {"artifacts": result}
