"""Bisect node comparison — per-node diff logic."""
from __future__ import annotations

import difflib
from typing import Any

from binex.stores.artifact_store import ArtifactStore
from binex.trace._compare import (
    FieldChange,
    compare_contents,
    get_artifact_content,
    get_artifact_contents,
    stringify,
)
from binex.trace.bisect import DivergencePoint, NodeComparison


def _check_status_divergence(
    task_id: str,
    good_by_task: dict[str, Any],
    bad_by_task: dict[str, Any],
) -> DivergencePoint | None:
    """Return a status DivergencePoint if statuses differ, else None."""
    from binex.trace.bisect import _get_upstream

    good_rec = good_by_task.get(task_id)
    bad_rec = bad_by_task.get(task_id)

    good_status = good_rec.status.value if good_rec else "missing"
    bad_status = bad_rec.status.value if bad_rec else "missing"

    if good_status != bad_status:
        upstream = _get_upstream(task_id, good_by_task, bad_by_task)
        return DivergencePoint(
            node_id=task_id,
            divergence_type="status",
            similarity=None,
            good_status=good_status,
            bad_status=bad_status,
            upstream_context=upstream,
        )
    return None


async def judge_text_pair(
    content_a: Any, content_b: Any, semantic_judge: Any,
) -> tuple[bool | None, str | None]:
    """Ask the judge whether two text outputs differ meaningfully.

    Returns ``(is_divergence, summary)``. ``is_divergence`` is None when the
    judge could not answer — the caller then falls back to the similarity
    threshold rather than silently treating the node as a match.
    """
    from binex.trace.semantic_diff import analyze_pair

    verdict = await analyze_pair(
        "", stringify(content_a) or "", stringify(content_b) or "", semantic_judge,
    )
    if verdict.error is not None:
        return None, f"could not analyze ({verdict.error})"
    return verdict.meaningful, verdict.summary


async def _content_verdict(
    art_store: ArtifactStore,
    good_rec: Any,
    bad_rec: Any,
    threshold: float,
    semantic_judge: Any | None,
) -> tuple[float | None, bool, list[FieldChange] | None, str | None]:
    """Decide whether one node's output diverged.

    Returns ``(similarity, is_divergence, field changes, judge summary)``.
    Structured content is settled field-wise and never reaches the judge.
    """
    content_a = await get_artifact_contents(art_store, good_rec.output_artifact_refs)
    content_b = await get_artifact_contents(art_store, bad_rec.output_artifact_refs)
    if content_a is None or content_b is None:
        return None, False, None, None

    similarity, changes = compare_contents(content_a, content_b)
    below_threshold = similarity < threshold

    # Text content with a judge: the ratio decides nothing, the judge does.
    if semantic_judge is not None and changes is None and similarity < 1.0:
        meaningful, summary = await judge_text_pair(
            content_a, content_b, semantic_judge,
        )
        if meaningful is not None:
            return similarity, meaningful, changes, summary
        return similarity, below_threshold, changes, summary

    return similarity, below_threshold, changes, None


async def _check_content_divergence(
    task_id: str,
    good_by_task: dict[str, Any],
    bad_by_task: dict[str, Any],
    art_store: ArtifactStore,
    threshold: float,
    semantic_judge: Any | None = None,
) -> DivergencePoint | None:
    """Return a content DivergencePoint if the outputs diverged, else None."""
    from binex.trace.bisect import _get_upstream

    good_rec = good_by_task.get(task_id)
    bad_rec = bad_by_task.get(task_id)

    good_status = good_rec.status.value if good_rec else "missing"
    bad_status = bad_rec.status.value if bad_rec else "missing"

    if good_status != "completed" or not good_rec or not bad_rec:
        return None

    similarity, is_divergence, _changes, summary = await _content_verdict(
        art_store, good_rec, bad_rec, threshold, semantic_judge,
    )
    if is_divergence:
        return DivergencePoint(
            node_id=task_id,
            divergence_type="content",
            similarity=round(similarity, 4) if similarity is not None else None,
            good_status=good_status,
            bad_status=bad_status,
            upstream_context=_get_upstream(task_id, good_by_task, bad_by_task),
            semantic_reason=summary,
        )
    return None


async def _compare_node(
    art_store: ArtifactStore,
    task_id: str,
    good_rec: Any,
    bad_rec: Any,
    threshold: float,
    semantic_judge: Any | None = None,
) -> NodeComparison:
    """Compare a single node between two runs."""
    g_status = good_rec.status.value if good_rec else None
    b_status = bad_rec.status.value if bad_rec else None

    comp_status = _determine_comp_status(good_rec, bad_rec, g_status, b_status)

    similarity, comp_status, changes, summary = await _check_content_similarity(
        art_store, comp_status, g_status, good_rec, bad_rec, threshold,
        semantic_judge,
    )

    node_diff = await _generate_content_diff(
        art_store, comp_status, good_rec, bad_rec, changes,
    )

    return NodeComparison(
        node_id=task_id,
        status=comp_status,
        good_status=g_status,
        bad_status=b_status,
        similarity=round(similarity, 4) if similarity is not None else None,
        latency_good_ms=good_rec.latency_ms if good_rec else None,
        latency_bad_ms=bad_rec.latency_ms if bad_rec else None,
        content_diff=node_diff,
        semantic_verdict=summary,
        field_changes=changes,
    )


def _determine_comp_status(
    good_rec: Any, bad_rec: Any,
    g_status: str | None, b_status: str | None,
) -> str:
    """Determine initial comparison status for a node pair."""
    if good_rec is None:
        return "missing_in_good"
    if bad_rec is None:
        return "missing_in_bad"
    if g_status != b_status:
        return "status_diff"
    return "match"


async def _check_content_similarity(
    art_store: ArtifactStore,
    comp_status: str,
    g_status: str | None,
    good_rec: Any,
    bad_rec: Any,
    threshold: float,
    semantic_judge: Any | None = None,
) -> tuple[float | None, str, list[FieldChange] | None, str | None]:
    """Check content similarity for matched-completed nodes.

    Returns (similarity, possibly-updated comp_status, field changes, judge
    summary). The changes are None when the contents were compared as text
    rather than field-wise — there is no per-field detail to report in that
    case; the summary is None when no judge ran.
    """
    if comp_status != "match" or g_status != "completed" or not good_rec or not bad_rec:
        return None, comp_status, None, None

    similarity, is_divergence, changes, summary = await _content_verdict(
        art_store, good_rec, bad_rec, threshold, semantic_judge,
    )
    if similarity is None:
        return None, comp_status, None, None
    if is_divergence:
        return similarity, "content_diff", changes, summary
    return round(similarity, 4), comp_status, changes, summary


async def _generate_content_diff(
    art_store: ArtifactStore,
    comp_status: str,
    good_rec: Any,
    bad_rec: Any,
    changes: list[FieldChange] | None,
) -> list[str] | None:
    """Describe how two nodes' outputs differ.

    Structured content yields one line per changed field ("which field moved");
    text content falls back to a unified diff.
    """
    if comp_status not in ("content_diff", "status_diff"):
        return None

    if changes:
        return [c.render() for c in changes]

    ca = await get_artifact_content(art_store, good_rec.output_artifact_refs) if good_rec else None
    cb = await get_artifact_content(art_store, bad_rec.output_artifact_refs) if bad_rec else None

    if ca is None and cb is None:
        return None

    node_diff = list(difflib.unified_diff(
        (ca or "").splitlines(keepends=True),
        (cb or "").splitlines(keepends=True),
        fromfile="good",
        tofile="bad",
        lineterm="",
    ))
    return node_diff or None


def _make_divergence(
    task_id: str,
    comparison: NodeComparison,
    good_by_task: dict[str, Any],
    bad_by_task: dict[str, Any],
) -> DivergencePoint:
    """Create a DivergencePoint from the first non-matching comparison."""
    from binex.trace.bisect import _get_upstream

    upstream = _get_upstream(task_id, good_by_task, bad_by_task)
    return DivergencePoint(
        node_id=task_id,
        divergence_type="content" if comparison.status == "content_diff" else "status",
        similarity=comparison.similarity,
        good_status=comparison.good_status or "missing",
        bad_status=comparison.bad_status or "missing",
        upstream_context=upstream,
        semantic_reason=comparison.semantic_verdict,
    )
