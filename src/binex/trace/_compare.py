"""Shared content comparison utilities for trace analysis.

Two comparison modes:

* **Structured** — when both sides are mappings/sequences (the usual shape of
  ``Artifact.content``), they are compared field by field. Reordering keys is
  not a change; flipping a value is, and the changed path is reported.
* **Text** — anything else falls back to :func:`content_similarity`, a
  character-level ratio.

The distinction matters because a character-level ratio is close to orthogonal
to "did the meaning change" on structured data, and anti-correlated on the
high-stakes cases: rewording moves many characters while preserving meaning,
whereas ``"approved" -> "rejected"`` moves few characters and inverts it. On the
old ``str(dict)`` path a reordered mapping scored 0.636 (flagged as a
divergence) while a flipped verdict scored 0.915 (passed as a match).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from binex.stores.artifact_store import ArtifactStore


@dataclass(frozen=True)
class FieldChange:
    """One differing leaf between two structured contents."""

    path: str
    before: Any
    after: Any
    kind: str  # "changed" | "added" | "removed"

    def render(self) -> str:
        """One-line human-readable form, e.g. ``decision: approved -> rejected``."""
        if self.kind == "added":
            return f"{self.path}: (absent) -> {self.after!r}"
        if self.kind == "removed":
            return f"{self.path}: {self.before!r} -> (absent)"
        return f"{self.path}: {self.before!r} -> {self.after!r}"


_MISSING = object()


def is_structured(content: Any) -> bool:
    """True if *content* carries structure worth comparing field-wise."""
    return isinstance(content, dict | list)


def flatten(content: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested mappings/sequences to ``{leaf_path: value}``.

    Empty containers are kept as leaves so that ``{"tags": []}`` and
    ``{"tags": ["x"]}`` compare as different rather than both vanishing.
    """
    if isinstance(content, dict) and content:
        out: dict[str, Any] = {}
        for key, value in content.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten(value, path))
        return out
    if isinstance(content, list) and content:
        out = {}
        for index, value in enumerate(content):
            out.update(flatten(value, f"{prefix}[{index}]"))
        return out
    return {prefix: content}


def compare_structured(a: Any, b: Any) -> tuple[float, list[FieldChange]]:
    """Compare two structured contents field by field.

    Returns ``(similarity, changes)`` where similarity is the fraction of leaf
    paths (union of both sides) that are unchanged, so key order never matters
    and every differing field is named.
    """
    flat_a, flat_b = flatten(a), flatten(b)
    paths = sorted(set(flat_a) | set(flat_b))
    if not paths:
        return 1.0, []

    changes: list[FieldChange] = []
    for path in paths:
        before = flat_a.get(path, _MISSING)
        after = flat_b.get(path, _MISSING)
        if before is _MISSING:
            changes.append(FieldChange(path, None, after, "added"))
        elif after is _MISSING:
            changes.append(FieldChange(path, before, None, "removed"))
        elif before != after:
            changes.append(FieldChange(path, before, after, "changed"))

    similarity = (len(paths) - len(changes)) / len(paths)
    return similarity, changes


def compare_contents(a: Any, b: Any) -> tuple[float, list[FieldChange] | None]:
    """Compare two artifact contents, structurally when possible.

    Returns ``(similarity, changes)``. ``changes is None`` means the comparison
    fell back to the character-level ratio — the caller has no field-level
    detail to show.
    """
    if a is None and b is None:
        return 1.0, None
    if is_structured(a) and is_structured(b):
        return compare_structured(a, b)
    return content_similarity(stringify(a), stringify(b)), None


def stringify(content: Any) -> str | None:
    """Render content for text comparison and unified diffs."""
    if content is None:
        return None
    return content if isinstance(content, str) else str(content)


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


async def get_artifact_contents(
    art_store: ArtifactStore,
    artifact_refs: list[str],
) -> Any:
    """Fetch artifact content with its structure intact.

    A single artifact yields its content as-is; several yield a list, so a node
    that emits multiple artifacts is still compared element-wise. Returns None
    when nothing is stored.
    """
    if not artifact_refs:
        return None
    contents: list[Any] = []
    for ref in artifact_refs:
        art = await art_store.get(ref)
        if art and art.content:
            contents.append(art.content)
    if not contents:
        return None
    return contents[0] if len(contents) == 1 else contents


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
