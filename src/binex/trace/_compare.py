"""Shared content comparison utilities for trace analysis."""
from __future__ import annotations

import difflib

from binex.stores.artifact_store import ArtifactStore


async def get_artifact_content(
    art_store: ArtifactStore,
    artifact_refs: list[str],
) -> str | None:
    """Fetch and concatenate content from artifact references.

    Returns None if refs is empty or no artifacts have content.
    """
    if not artifact_refs:
        return None
    parts: list[str] = []
    for ref in artifact_refs:
        art = await art_store.get(ref)
        if art and art.content:
            parts.append(str(art.content))
    return "\n".join(parts) if parts else None


def content_similarity(a: str | None, b: str | None) -> float:
    """Compute similarity ratio between two strings (0.0 to 1.0).

    Handles None values: both None = 1.0, one None = 0.0.
    """
    if a is None and b is None:
        return 1.0
    if a is None or b is None:
        return 0.0
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()
