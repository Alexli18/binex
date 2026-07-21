"""Lineage API endpoint for Binex Web UI."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.artifacts.binary import is_binary_artifact
from binex.cli import get_stores
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore

router = APIRouter(prefix="/runs", tags=["lineage"])


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/{run_id}/lineage")
async def get_lineage(run_id: str) -> JSONResponse:
    """Artifact lineage graph for a workflow run."""
    exec_store, art_store = _get_stores()
    try:
        artifacts = await art_store.list_by_run(run_id)

        nodes = []
        edges = []
        seen_ids: set[str] = set()

        for art in artifacts:
            if art.id not in seen_ids:
                seen_ids.add(art.id)
                node = {
                    "id": art.id,
                    "type": art.type,
                    "content": art.content,
                    "produced_by": art.lineage.produced_by,
                }
                # Flag binary artifacts so the UI can render a thumbnail (#76).
                if is_binary_artifact(art):
                    node["binary"] = True
                    node["mime"] = art.content.get("mime")
                    node["blob_url"] = (
                        f"/api/v1/runs/{run_id}/artifacts/{art.id}/blob"
                    )
                nodes.append(node)

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
    finally:
        await exec_store.close()
