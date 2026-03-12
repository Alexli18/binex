"""Run bisection — find the first node where two runs diverge."""
from __future__ import annotations

from dataclasses import dataclass, field

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
        )
        node_map.append(comparison)

        if divergence is None and comparison.status != "match":
            divergence = _make_divergence(
                task_id, comparison, good_by_task, bad_by_task,
            )
            divergence_idx = i

    return node_map, divergence, divergence_idx


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
