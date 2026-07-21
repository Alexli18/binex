"""Binary artifacts — content-addressed media payloads as node outputs (#76).

An artifact is a JSON envelope plus (for binaries) a content-addressed payload.
JSON artifacts are unchanged; a binary artifact's ``content`` is the envelope::

    {"kind": "binary", "mime": "image/png", "size": 12345,
     "sha256": "<hex>", "path": "/abs/.../blobs/<sha256>"}

The payload lives at ``<store>/artifacts/blobs/<sha256>``. Content addressing
gives free deduplication (an asset flowing through five nodes is stored once)
and a ready-made cache key — the sha256 is already in the envelope, so node
caching (#68), which hashes artifact content, picks it up for free.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from pathlib import Path
from typing import Any

from binex.models.artifact import Artifact, Lineage

BINARY_KIND = "binary"
DEFAULT_MAX_BLOB_BYTES = 100 * 1024 * 1024  # 100 MB


def blob_dir(store_path: str | None = None) -> Path:
    """Directory holding content-addressed blobs."""
    if store_path is None:
        from binex.settings import Settings

        store_path = Settings().store_path
    return Path(store_path) / "artifacts" / "blobs"


def store_blob(
    data: bytes,
    *,
    store_path: str | None = None,
    max_bytes: int = DEFAULT_MAX_BLOB_BYTES,
) -> tuple[str, Path]:
    """Write ``data`` to the content-addressed store (dedup). Returns (sha256, path)."""
    if len(data) > max_bytes:
        raise ValueError(
            f"binary artifact is {len(data)} bytes, exceeds limit {max_bytes}"
        )
    sha = hashlib.sha256(data).hexdigest()
    directory = blob_dir(store_path)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / sha
    if not path.exists():  # dedup: identical content is written once
        path.write_bytes(data)
    return sha, path


def make_binary_artifact(
    run_id: str,
    produced_by: str,
    data: bytes,
    mime: str,
    *,
    store_path: str | None = None,
    max_bytes: int = DEFAULT_MAX_BLOB_BYTES,
    derived_from: list[str] | None = None,
    artifact_id: str | None = None,
) -> Artifact:
    """Build a binary Artifact from raw bytes, storing the payload as a blob."""
    sha, path = store_blob(data, store_path=store_path, max_bytes=max_bytes)
    envelope: dict[str, Any] = {
        "kind": BINARY_KIND,
        "mime": mime,
        "size": len(data),
        "sha256": sha,
        "path": str(path.resolve()),
    }
    return Artifact(
        id=artifact_id or f"art_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        type="binary",
        content=envelope,
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


def is_binary_artifact(artifact: Artifact) -> bool:
    c = artifact.content
    return isinstance(c, dict) and c.get("kind") == BINARY_KIND


def binary_envelope(artifact: Artifact) -> dict[str, Any] | None:
    return artifact.content if is_binary_artifact(artifact) else None


def load_blob(envelope: dict[str, Any]) -> bytes:
    """Read a binary payload from its envelope."""
    return Path(envelope["path"]).read_bytes()


def to_data_uri(envelope: dict[str, Any]) -> str:
    """Encode a binary payload as a ``data:`` URI (for LiteLLM image messages)."""
    b64 = base64.b64encode(load_blob(envelope)).decode()
    return f"data:{envelope['mime']};base64,{b64}"


def binary_descriptor(envelope: dict[str, Any], produced_by: str = "") -> str:
    """A one-line textual descriptor for models that can't consume the payload."""
    src = f" from node '{produced_by}'" if produced_by else ""
    return (
        f"[binary artifact: {envelope.get('mime', 'application/octet-stream')}, "
        f"{envelope.get('size', 0)} bytes, sha256:{str(envelope.get('sha256', ''))[:12]}"
        f"{src}]"
    )


__all__ = [
    "BINARY_KIND",
    "DEFAULT_MAX_BLOB_BYTES",
    "binary_descriptor",
    "binary_envelope",
    "blob_dir",
    "is_binary_artifact",
    "load_blob",
    "make_binary_artifact",
    "store_blob",
    "to_data_uri",
]
