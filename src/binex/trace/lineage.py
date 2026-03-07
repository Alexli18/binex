"""Artifact lineage traversal — build provenance trees."""

from __future__ import annotations

from typing import Any

from binex.stores.artifact_store import ArtifactStore


async def build_lineage_tree(
    store: ArtifactStore, artifact_id: str
) -> dict[str, Any] | None:
    """Build a recursive provenance tree for an artifact.

    Returns a dict with keys: artifact_id, type, produced_by, parents.
    Each parent is itself a tree node (recursive).
    Returns None if the artifact doesn't exist.
    """
    artifact = await store.get(artifact_id)
    if artifact is None:
        return None

    parents: list[dict[str, Any]] = []
    for parent_id in artifact.lineage.derived_from:
        parent_tree = await build_lineage_tree(store, parent_id)
        if parent_tree is not None:
            parents.append(parent_tree)

    return {
        "artifact_id": artifact.id,
        "type": artifact.type,
        "produced_by": artifact.lineage.produced_by,
        "parents": parents,
    }


def format_lineage_tree(tree: dict[str, Any], indent: int = 0) -> str:
    """Render a lineage tree as a human-readable tree view."""
    if tree is None:
        return ""

    lines: list[str] = []
    prefix = ""
    if indent > 0:
        prefix = "  " * (indent - 1) + "└── "

    label = f"{tree['artifact_id']} (type={tree['type']}, produced_by={tree['produced_by']})"
    lines.append(f"{prefix}{label}")

    for parent in tree["parents"]:
        lines.append(format_lineage_tree(parent, indent + 1))

    return "\n".join(lines)
