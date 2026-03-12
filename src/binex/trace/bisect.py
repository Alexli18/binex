"""Run bisection — find the first node where two runs diverge."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any

from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DivergencePoint:
    node_id: str
    divergence_type: str  # "status" or "content"
    similarity: float | None  # None for status divergence
    good_status: str
    bad_status: str
    upstream_context: list[str] = field(default_factory=list)


@dataclass
class NodeComparison:
    """Per-node comparison result."""
    node_id: str
    status: str  # "match", "status_diff", "content_diff", "missing_in_good", "missing_in_bad"
    good_status: str | None
    bad_status: str | None
    similarity: float | None = None
    latency_good_ms: int | None = None
    latency_bad_ms: int | None = None
    content_diff: list[str] | None = None


@dataclass
class ErrorContext:
    """Error details at divergence point."""
    node_id: str
    error_message: str
    pattern: str  # reuses classify_error() from diagnose


@dataclass
class BisectReport:
    """Complete bisect analysis report."""
    good_run_id: str
    bad_run_id: str
    workflow_name: str
    divergence_point: DivergencePoint | None
    node_map: list[NodeComparison] = field(default_factory=list)
    error_context: ErrorContext | None = None
    downstream_impact: list[str] = field(default_factory=list)


async def find_divergence(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    good_run_id: str,
    bad_run_id: str,
    threshold: float = 0.9,
) -> DivergencePoint | None:
    """Find the first node where two runs diverge.

    Args:
        exec_store: Execution store
        art_store: Artifact store
        good_run_id: ID of the known good run
        bad_run_id: ID of the known bad run
        threshold: Content similarity threshold (0.0-1.0). Below this = divergence.

    Returns:
        DivergencePoint or None if no divergence found.

    Raises:
        ValueError: If run not found or workflows don't match.
    """
    # Load both runs
    good_run = await exec_store.get_run(good_run_id)
    if good_run is None:
        raise ValueError(f"Run '{good_run_id}' not found")

    bad_run = await exec_store.get_run(bad_run_id)
    if bad_run is None:
        raise ValueError(f"Run '{bad_run_id}' not found")

    # Verify same workflow
    if good_run.workflow_name != bad_run.workflow_name:
        raise ValueError(
            f"Workflows don't match: '{good_run.workflow_name}' vs '{bad_run.workflow_name}'"
        )

    # Load execution records
    good_records = await exec_store.list_records(good_run_id)
    bad_records = await exec_store.list_records(bad_run_id)

    good_by_task = {r.task_id: r for r in good_records}
    bad_by_task = {r.task_id: r for r in bad_records}

    # Walk nodes in order (use good run order as reference)
    all_tasks: list[str] = []
    seen: set[str] = set()
    for r in good_records:
        if r.task_id not in seen:
            all_tasks.append(r.task_id)
            seen.add(r.task_id)
    for r in bad_records:
        if r.task_id not in seen:
            all_tasks.append(r.task_id)
            seen.add(r.task_id)

    for task_id in all_tasks:
        # Check status divergence first
        point = _check_status_divergence(task_id, good_by_task, bad_by_task)
        if point is not None:
            return point

        # Then check content divergence
        point = await _check_content_divergence(
            task_id, good_by_task, bad_by_task, art_store, threshold,
        )
        if point is not None:
            return point

    return None  # No divergence found


def _check_status_divergence(
    task_id: str,
    good_by_task: dict,
    bad_by_task: dict,
) -> DivergencePoint | None:
    """Return a status DivergencePoint if statuses differ, else None."""
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
    good_rec = good_by_task.get(task_id)
    bad_rec = bad_by_task.get(task_id)

    good_status = good_rec.status.value if good_rec else "missing"
    bad_status = bad_rec.status.value if bad_rec else "missing"

    if good_status != "completed" or not good_rec or not bad_rec:
        return None

    content_a = await _get_content(art_store, good_rec.output_artifact_refs)
    content_b = await _get_content(art_store, bad_rec.output_artifact_refs)

    if content_a is None or content_b is None:
        return None

    similarity = difflib.SequenceMatcher(None, content_a, content_b).ratio()
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


def _get_upstream(
    task_id: str,
    good_by_task: dict,
    bad_by_task: dict,
) -> list[str]:
    """Get upstream node IDs from input artifact refs."""
    rec = good_by_task.get(task_id) or bad_by_task.get(task_id)
    if not rec:
        return []
    upstream: list[str] = []
    for tid, r in good_by_task.items():
        if tid != task_id and r.output_artifact_refs:
            for ref in r.output_artifact_refs:
                if rec.input_artifact_refs and ref in rec.input_artifact_refs:
                    upstream.append(tid)
    return upstream


async def _get_content(art_store: ArtifactStore, refs: list[str]) -> str | None:
    """Get concatenated artifact content."""
    if not refs:
        return None
    parts: list[str] = []
    for ref in refs:
        art = await art_store.get(ref)
        if art and art.content:
            parts.append(str(art.content))
    return "\n".join(parts) if parts else None


def divergence_to_dict(
    good_run_id: str,
    bad_run_id: str,
    divergence: DivergencePoint | None,
) -> dict[str, Any]:
    """Convert bisect result to JSON-serializable dict."""
    result: dict[str, Any] = {
        "good_run_id": good_run_id,
        "bad_run_id": bad_run_id,
    }
    if divergence is None:
        result["divergence"] = None
        result["message"] = "No divergence found"
    else:
        result["divergence"] = {
            "node_id": divergence.node_id,
            "divergence_type": divergence.divergence_type,
            "similarity": divergence.similarity,
            "good_status": divergence.good_status,
            "bad_status": divergence.bad_status,
            "upstream_context": divergence.upstream_context,
        }
    return result


# ---------------------------------------------------------------------------
# Full bisect report
# ---------------------------------------------------------------------------

async def bisect_report(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    good_run_id: str,
    bad_run_id: str,
    threshold: float = 0.9,
) -> BisectReport:
    """Build a complete bisect report comparing two runs.

    Single pass through stores: builds node_map, finds divergence,
    generates content_diff, collects error_context and downstream_impact.
    """
    good_run, bad_run = await _load_and_validate_runs(
        exec_store, good_run_id, bad_run_id,
    )

    good_records = await exec_store.list_records(good_run_id)
    bad_records = await exec_store.list_records(bad_run_id)

    good_by_task = {r.task_id: r for r in good_records}
    bad_by_task = {r.task_id: r for r in bad_records}

    all_tasks = _ordered_task_ids(good_records, bad_records)

    node_map, divergence, divergence_idx = await _build_node_map(
        art_store, all_tasks, good_by_task, bad_by_task, threshold,
    )

    error_ctx = _build_error_context(divergence, bad_by_task)

    downstream: list[str] = []
    if divergence_idx is not None:
        downstream = [
            nc.node_id
            for nc in node_map[divergence_idx + 1:]
            if nc.status != "match"
        ]

    return BisectReport(
        good_run_id=good_run_id,
        bad_run_id=bad_run_id,
        workflow_name=good_run.workflow_name,
        divergence_point=divergence,
        node_map=node_map,
        error_context=error_ctx,
        downstream_impact=downstream,
    )


async def _load_and_validate_runs(
    exec_store: ExecutionStore,
    good_run_id: str,
    bad_run_id: str,
) -> tuple:
    """Load two runs and validate they exist and share the same workflow."""
    good_run = await exec_store.get_run(good_run_id)
    if good_run is None:
        raise ValueError(f"Run '{good_run_id}' not found")
    bad_run = await exec_store.get_run(bad_run_id)
    if bad_run is None:
        raise ValueError(f"Run '{bad_run_id}' not found")
    if good_run.workflow_name != bad_run.workflow_name:
        raise ValueError(
            f"Workflows don't match: "
            f"'{good_run.workflow_name}' vs '{bad_run.workflow_name}'"
        )
    return good_run, bad_run


async def _build_node_map(
    art_store: ArtifactStore,
    all_tasks: list[str],
    good_by_task: dict,
    bad_by_task: dict,
    threshold: float,
) -> tuple[list[NodeComparison], DivergencePoint | None, int | None]:
    """Single pass: build node_map and find first divergence point."""
    node_map: list[NodeComparison] = []
    divergence: DivergencePoint | None = None
    divergence_idx: int | None = None

    for i, task_id in enumerate(all_tasks):
        comparison = await _compare_node(
            art_store, task_id,
            good_by_task.get(task_id),
            bad_by_task.get(task_id),
            threshold,
        )
        node_map.append(comparison)

        if divergence is None and comparison.status != "match":
            divergence = _make_divergence(
                task_id, comparison, good_by_task, bad_by_task,
            )
            divergence_idx = i

    return node_map, divergence, divergence_idx


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

    ca = await _get_content(art_store, good_rec.output_artifact_refs)
    cb = await _get_content(art_store, bad_rec.output_artifact_refs)
    if ca is None or cb is None:
        return None, comp_status, ca, cb

    similarity = difflib.SequenceMatcher(None, ca, cb).ratio()
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
        ca = await _get_content(art_store, good_rec.output_artifact_refs)
    if cb is None and bad_rec:
        cb = await _get_content(art_store, bad_rec.output_artifact_refs)

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
    upstream = _get_upstream(task_id, good_by_task, bad_by_task)
    return DivergencePoint(
        node_id=task_id,
        divergence_type="content" if comparison.status == "content_diff" else "status",
        similarity=comparison.similarity,
        good_status=comparison.good_status or "missing",
        bad_status=comparison.bad_status or "missing",
        upstream_context=upstream,
    )


def _build_error_context(
    divergence: DivergencePoint | None,
    bad_by_task: dict,
) -> ErrorContext | None:
    """Build error context from the divergence point's bad record."""
    if divergence is None:
        return None
    from binex.trace.diagnose import classify_error
    bad_rec = bad_by_task.get(divergence.node_id)
    if not bad_rec or not bad_rec.error:
        return None
    return ErrorContext(
        node_id=divergence.node_id,
        error_message=bad_rec.error,
        pattern=classify_error(bad_rec.error),
    )


def _ordered_task_ids(good_records, bad_records) -> list[str]:
    """Build ordered list of all task IDs from both runs."""
    all_tasks: list[str] = []
    seen: set[str] = set()
    for r in good_records:
        if r.task_id not in seen:
            all_tasks.append(r.task_id)
            seen.add(r.task_id)
    for r in bad_records:
        if r.task_id not in seen:
            all_tasks.append(r.task_id)
            seen.add(r.task_id)
    return all_tasks


def bisect_report_to_dict(report: BisectReport) -> dict[str, Any]:
    """Convert a BisectReport to a JSON-serializable dict."""
    result: dict[str, Any] = {
        "good_run_id": report.good_run_id,
        "bad_run_id": report.bad_run_id,
        "workflow_name": report.workflow_name,
    }

    if report.divergence_point is None:
        result["divergence"] = None
        result["message"] = "No divergence found"
    else:
        dp = report.divergence_point
        result["divergence"] = {
            "node_id": dp.node_id,
            "divergence_type": dp.divergence_type,
            "similarity": dp.similarity,
            "good_status": dp.good_status,
            "bad_status": dp.bad_status,
            "upstream_context": dp.upstream_context,
        }

    result["node_map"] = [
        {
            "node_id": nc.node_id,
            "status": nc.status,
            "good_status": nc.good_status,
            "bad_status": nc.bad_status,
            "similarity": nc.similarity,
            "latency_good_ms": nc.latency_good_ms,
            "latency_bad_ms": nc.latency_bad_ms,
            "content_diff": nc.content_diff,
        }
        for nc in report.node_map
    ]

    result["error_context"] = (
        {
            "node_id": report.error_context.node_id,
            "error_message": report.error_context.error_message,
            "pattern": report.error_context.pattern,
        }
        if report.error_context
        else None
    )

    result["downstream_impact"] = report.downstream_impact

    return result
