"""Artifacts API endpoint — includes binary-blob serving for previews (#76 UI)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response

from binex.artifacts.binary import is_binary_artifact, load_blob
from binex.cli import get_stores
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore

router = APIRouter()


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/runs/{run_id}/artifacts")
async def get_artifacts(run_id: str) -> dict[str, Any]:
    """Return all artifacts for a given run.

    Binary artifacts (#76) carry a ``binary: true`` flag and a ``blob_url`` the
    UI can point an ``<img>`` / ``<audio>`` / download link at; their ``content``
    stays the envelope (mime/size/sha256), never the raw bytes.
    """
    exec_store, art_store = _get_stores()
    try:
        artifacts = await art_store.list_by_run(run_id)
        result = []
        for art in artifacts:
            derived = art.lineage.derived_from if art.lineage.derived_from else None
            item: dict[str, Any] = {
                "id": art.id,
                "type": art.type,
                "content": art.content,
                "lineage": {
                    "produced_by": art.lineage.produced_by,
                    "step": 0,
                    "derived_from": derived,
                },
            }
            if is_binary_artifact(art):
                item["binary"] = True
                item["mime"] = art.content.get("mime")
                item["size"] = art.content.get("size")
                item["blob_url"] = (
                    f"/api/v1/runs/{run_id}/artifacts/{art.id}/blob"
                )
            result.append(item)
        return {"artifacts": result}
    finally:
        await exec_store.close()


@router.get("/runs/{run_id}/artifacts/{artifact_id}/blob")
async def get_artifact_blob(run_id: str, artifact_id: str) -> Response:
    """Serve a binary artifact's raw payload with its mime type (for previews)."""
    exec_store, art_store = _get_stores()
    try:
        artifacts = await art_store.list_by_run(run_id)
        art = next((a for a in artifacts if a.id == artifact_id), None)
        if art is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        if not is_binary_artifact(art):
            raise HTTPException(status_code=400, detail="artifact is not binary")
        try:
            data = load_blob(art.content)
        except OSError as exc:
            raise HTTPException(status_code=404, detail="blob missing") from exc
        mime = str(art.content.get("mime") or "application/octet-stream")
        return Response(content=data, media_type=mime)
    finally:
        await exec_store.close()
