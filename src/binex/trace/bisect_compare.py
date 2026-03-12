"""Bisect node comparison — per-node diff logic."""
from __future__ import annotations

import difflib

from binex.stores.artifact_store import ArtifactStore
from binex.trace._compare import content_similarity, get_artifact_content
from binex.trace.bisect import DivergencePoint, NodeComparison


def _check_status_divergence(
    task_id: str,
    good_by_task: dict,
    bad_by_task: dict,
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


async def _check_content_divergence(
    task_id: str,
    good_by_task: dict,
    bad_by_task: dict,
    art_store: ArtifactStore,
    threshold: float,
) -> DivergencePoint | None:
    """Return a content DivergencePoint if content similarity is below threshold, else None."""
    from binex.trace.bisect import _get_upstream

    good_rec = good_by_task.get(task_id)
    bad_rec = bad_by_task.get(task_id)

    good_status = good_rec.status.value if good_rec else "missing"
    bad_status = bad_rec.status.value if bad_rec else "missing"

    if good_status != "completed" or not good_rec or not bad_rec:
        return None

    content_a = await get_artifact_content(art_store, good_rec.output_artifact_refs)
    content_b = await get_artifact_content(art_store, bad_rec.output_artifact_refs)

    if content_a is None or content_b is None:
        return None

    similarity = content_similarity(content_a, content_b)
    if similarity < threshold:
        upstream = _get_upstream(task_id, good_by_task, bad_by_task)
        return DivergencePoint(
            node_id=task_id,
            divergence_type="content",
            similarity=round(similarity, 4),
            good_status=good_status,
            bad_status=bad_status,
            upstream_context=upstream,
        )
    return None


async def _compare_node(
    art_store: ArtifactStore,
    task_id: str,
    good_rec,
    bad_rec,
    threshold: float,
) -> NodeComparison:
    """Compare a single node between two runs."""
    g_status = good_rec.status.value if good_rec else None
    b_status = bad_rec.status.value if bad_rec else None

    comp_status = _determine_comp_status(good_rec, bad_rec, g_status, b_status)

    similarity, comp_status, ca, cb = await _check_content_similarity(
        art_store, comp_status, g_status, good_rec, bad_rec, threshold,
    )

    node_diff = await _generate_content_diff(
        art_store, comp_status, good_rec, bad_rec, ca, cb,
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
    )


def _determine_comp_status(good_rec, bad_rec, g_status, b_status) -> str:
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
    good_rec,
    bad_rec,
    threshold: float,
) -> tuple[float | None, str, str | None, str | None]:
    """Check content similarity for matched-completed nodes.

    Returns (similarity, possibly-updated comp_status, content_a, content_b).
    """
    if comp_status != "match" or g_status != "completed" or not good_rec or not bad_rec:
        return None, comp_status, None, None

    ca = await get_artifact_content(art_store, good_rec.output_artifact_refs)
    cb = await get_artifact_content(art_store, bad_rec.output_artifact_refs)
    if ca is None or cb is None:
        return None, comp_status, ca, cb

    similarity = content_similarity(ca, cb)
    if similarity < threshold:
        return similarity, "content_diff", ca, cb
    return round(similarity, 4), comp_status, ca, cb


async def _generate_content_diff(
    art_store: ArtifactStore,
    comp_status: str,
    good_rec,
    bad_rec,
    ca: str | None,
    cb: str | None,
) -> list[str] | None:
    """Generate unified diff for nodes that differ."""
    if comp_status not in ("content_diff", "status_diff"):
        return None

    if ca is None and good_rec:
        ca = await get_artifact_content(art_store, good_rec.output_artifact_refs)
    if cb is None and bad_rec:
        cb = await get_artifact_content(art_store, bad_rec.output_artifact_refs)

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
    good_by_task: dict,
    bad_by_task: dict,
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
    )
