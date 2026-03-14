"""Lineage API endpoint for Binex Web UI."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.cli import get_stores

router = APIRouter(prefix="/runs", tags=["lineage"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/{run_id}/lineage")
async def get_lineage(run_id: str) -> JSONResponse:
    """Artifact lineage graph for a workflow run."""
    _, art_store = _get_stores()

    artifacts = await art_store.list_by_run(run_id)

    nodes = []
    edges = []
    seen_ids: set[str] = set()

    for art in artifacts:
        if art.id not in seen_ids:
            seen_ids.add(art.id)
            nodes.append({
                "id": art.id,
                "type": art.type,
                "content": art.content,
                "produced_by": art.lineage.produced_by,
            })

        # Build edges from derived_from
        if art.lineage.derived_from:
            for parent_id in art.lineage.derived_from:
                edges.append({
                    "source": parent_id,
                    "target": art.id,
                })

    return JSONResponse({
        "run_id": run_id,
        "nodes": nodes,
        "edges": edges,
    })
