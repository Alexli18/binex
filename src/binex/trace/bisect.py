"""Run bisection — find the first node where two runs diverge."""
from __future__ import annotations

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
    # Why the judge called this a real change, when --semantic was used.
    semantic_reason: str | None = None


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
    # Judge summary when --semantic was used, e.g. "cosmetic only (reworded
    # /reformatted, same substance)". None when the node was never judged.
    semantic_verdict: str | None = None


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


# ---------------------------------------------------------------------------
# Re-exports for backward compatibility
# ---------------------------------------------------------------------------
from binex.trace.bisect_compare import (  # noqa: E402, F401, I001
    _check_status_divergence, _check_content_divergence,
)
from binex.trace.bisect_format import bisect_report_to_dict, divergence_to_dict  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


async def find_divergence(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    good_run_id: str,
    bad_run_id: str,
    threshold: float = 0.9,
    semantic_judge: Any | None = None,
) -> DivergencePoint | None:
    """Find the first node where two runs diverge.

    Args:
        exec_store: Execution store
        art_store: Artifact store
        good_run_id: ID of the known good run
        bad_run_id: ID of the known bad run
        threshold: Content similarity threshold (0.0-1.0). Below this = divergence.
        semantic_judge: Optional async judge. When given, it — not *threshold* —
            decides every text node whose output differs at all. Structured
            content is still compared field-wise, which is exact and free. The
            walk stops at the first meaningful divergence, so the judge is asked
            about at most the nodes up to it.

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

    # Walk nodes in dependency order so "first divergence" means upstream-most.
    all_tasks = _ordered_task_ids(good_records, bad_records)

    for task_id in all_tasks:
        # Check status divergence first
        point = _check_status_divergence(task_id, good_by_task, bad_by_task)
        if point is not None:
            return point

        # Then check content divergence
        point = await _check_content_divergence(
            task_id, good_by_task, bad_by_task, art_store, threshold,
            semantic_judge=semantic_judge,
        )
        if point is not None:
            return point

    return None  # No divergence found


def _get_upstream(
    task_id: str,
    good_by_task: dict[str, Any],
    bad_by_task: dict[str, Any],
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


# ---------------------------------------------------------------------------
# Full bisect report
# ---------------------------------------------------------------------------

async def bisect_report(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    good_run_id: str,
    bad_run_id: str,
    threshold: float = 0.9,
    semantic_judge: Any | None = None,
) -> BisectReport:
    """Build a complete bisect report comparing two runs.

    Single pass through stores: builds node_map, finds divergence,
    generates content_diff, collects error_context and downstream_impact.

    With *semantic_judge*, text nodes are decided by the judge rather than by
    *threshold*; see :func:`find_divergence`.
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
        semantic_judge,
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
) -> tuple[Any, Any]:
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
    good_by_task: dict[str, Any],
    bad_by_task: dict[str, Any],
    threshold: float,
    semantic_judge: Any | None = None,
) -> tuple[list[NodeComparison], DivergencePoint | None, int | None]:
    """Single pass: build node_map and find first divergence point.

    The judge is dropped once a divergence is found: every node after it is a
    consequence, not the cause, so paying to classify them would be waste. Those
    nodes still get their text similarity, marked "not judged".
    """
    from binex.trace.bisect_compare import _compare_node, _make_divergence

    node_map: list[NodeComparison] = []
    divergence: DivergencePoint | None = None
    divergence_idx: int | None = None

    for i, task_id in enumerate(all_tasks):
        comparison = await _compare_node(
            art_store, task_id,
            good_by_task.get(task_id),
            bad_by_task.get(task_id),
            threshold,
            semantic_judge if divergence is None else None,
        )
        if semantic_judge is not None and divergence is not None:
            comparison.semantic_verdict = "not judged (downstream of divergence)"
        node_map.append(comparison)

        if divergence is None and comparison.status != "match":
            divergence = _make_divergence(
                task_id, comparison, good_by_task, bad_by_task,
            )
            divergence_idx = i

    return node_map, divergence, divergence_idx


async def semantic_candidates(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    good_run_id: str,
    bad_run_id: str,
) -> list[tuple[str, str, str]]:
    """Nodes a semantic bisect could spend a judge call on.

    Only text content that actually differs qualifies: identical outputs and
    structured content are settled without a model. Used for the pre-flight cost
    estimate, so it is an upper bound — the walk stops at the first divergence.
    """
    from binex.trace._compare import compare_contents, get_artifact_contents, stringify

    good_records = await exec_store.list_records(good_run_id)
    bad_records = await exec_store.list_records(bad_run_id)
    good_by_task = {r.task_id: r for r in good_records}
    bad_by_task = {r.task_id: r for r in bad_records}

    pairs: list[tuple[str, str, str]] = []
    for task_id in _ordered_task_ids(good_records, bad_records):
        good_rec, bad_rec = good_by_task.get(task_id), bad_by_task.get(task_id)
        if not good_rec or not bad_rec:
            continue
        if good_rec.status.value != "completed" or bad_rec.status.value != "completed":
            continue
        a = await get_artifact_contents(art_store, good_rec.output_artifact_refs)
        b = await get_artifact_contents(art_store, bad_rec.output_artifact_refs)
        if a is None or b is None:
            continue
        similarity, changes = compare_contents(a, b)
        if changes is None and similarity < 1.0:
            pairs.append((task_id, stringify(a) or "", stringify(b) or ""))
    return pairs


def _build_error_context(
    divergence: DivergencePoint | None,
    bad_by_task: dict[str, Any],
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


def _infer_edges(records: list[Any]) -> set[tuple[str, str]]:
    """Recover producer -> consumer edges from artifact references.

    The workflow file is not needed (and is not available for every run): the
    execution records already say which artifacts a node consumed and produced.
    """
    produced_by: dict[str, str] = {}
    for r in records:
        for ref in r.output_artifact_refs or []:
            produced_by[ref] = r.task_id

    edges: set[tuple[str, str]] = set()
    for r in records:
        for ref in r.input_artifact_refs or []:
            producer = produced_by.get(ref)
            if producer is not None and producer != r.task_id:
                edges.add((producer, r.task_id))
    return edges


def _topological(nodes: list[str], edges: set[tuple[str, str]]) -> list[str]:
    """Sort *nodes* so dependencies precede dependents.

    Nodes at the same depth (fan-out siblings, or nodes with no recoverable
    edges at all) are ordered by task id rather than by the order the store
    returned them: completion order is a race, so tie-breaking on it would make
    "the first divergence" flip between siblings from one run to the next.

    A cycle — which the validator forbids, but an imported trace can still
    contain — degrades to id order for whatever is left rather than dropping
    nodes.
    """
    known = set(nodes)
    indegree = dict.fromkeys(nodes, 0)
    dependents: dict[str, list[str]] = {node: [] for node in nodes}
    for producer, consumer in edges:
        if producer not in known or consumer not in known:
            continue
        dependents[producer].append(consumer)
        indegree[consumer] += 1

    remaining = set(nodes)
    ordered: list[str] = []
    while remaining:
        ready = sorted(n for n in remaining if indegree[n] == 0)
        if not ready:  # cycle
            ordered.extend(sorted(remaining))
            break
        for node in ready:
            ordered.append(node)
            remaining.discard(node)
            for dependent in dependents[node]:
                indegree[dependent] -= 1
    return ordered


def _ordered_task_ids(good_records: list[Any], bad_records: list[Any]) -> list[str]:
    """All task IDs from both runs, in dependency order.

    "The first node where the runs diverge" is only meaningful along the DAG.
    Following store-insertion order instead makes the answer depend on which
    fan-out branch happened to finish first.
    """
    all_tasks: list[str] = []
    seen: set[str] = set()
    for r in [*good_records, *bad_records]:
        if r.task_id not in seen:
            all_tasks.append(r.task_id)
            seen.add(r.task_id)

    edges = _infer_edges(good_records) | _infer_edges(bad_records)
    return _topological(all_tasks, edges)
