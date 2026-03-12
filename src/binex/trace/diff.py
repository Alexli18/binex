"""Run diff comparison — compare two runs step-by-step."""

from __future__ import annotations

from typing import Any

from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore
from binex.trace._compare import content_similarity, get_artifact_content


def _compute_summary(steps: list[dict]) -> dict:
    """Compute aggregate diff summary from steps."""
    total = len(steps)
    changed = sum(
        1 for s in steps
        if s["status_changed"] or s["artifacts_changed"] or s.get("content_similarity", 1.0) < 1.0
    )

    latency_delta = 0.0
    for s in steps:
        if s["latency_a"] is not None and s["latency_b"] is not None:
            latency_delta += s["latency_b"] - s["latency_a"]

    similarities = [s.get("content_similarity", 1.0) for s in steps]
    avg_similarity = sum(similarities) / len(similarities) if similarities else 1.0

    return {
        "total_nodes": total,
        "changed_nodes": changed,
        "unchanged_nodes": total - changed,
        "latency_delta_ms": latency_delta,
        "cost_delta": 0.0,  # TODO: compute from cost_records when available
        "content_similarity": round(avg_similarity, 4),
    }


async def _compare_single_task(
    art_store: ArtifactStore,
    task_id: str,
    rec_a: Any | None,
    rec_b: Any | None,
) -> dict[str, Any]:
    """Compare a single task across two runs — artifact fetching, similarity, status."""
    status_a = rec_a.status.value if rec_a else None
    status_b = rec_b.status.value if rec_b else None
    latency_a = rec_a.latency_ms if rec_a else None
    latency_b = rec_b.latency_ms if rec_b else None
    agent_a = rec_a.agent_id if rec_a else None
    agent_b = rec_b.agent_id if rec_b else None

    refs_a = rec_a.output_artifact_refs if rec_a else []
    refs_b = rec_b.output_artifact_refs if rec_b else []

    artifacts_changed = await _artifacts_differ(art_store, refs_a, refs_b)
    content_a = await get_artifact_content(art_store, refs_a)
    content_b = await get_artifact_content(art_store, refs_b)
    similarity = content_similarity(content_a, content_b)

    return {
        "task_id": task_id,
        "status_a": status_a,
        "status_b": status_b,
        "status_changed": status_a != status_b,
        "latency_a": latency_a,
        "latency_b": latency_b,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "agent_changed": agent_a != agent_b,
        "artifacts_changed": artifacts_changed,
        "error_a": rec_a.error if rec_a else None,
        "error_b": rec_b.error if rec_b else None,
        "content_a": content_a,
        "content_b": content_b,
        "content_similarity": similarity,
    }


async def diff_runs(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    run_id_a: str,
    run_id_b: str,
) -> dict[str, Any]:
    """Compare two runs step-by-step: artifact differences, execution metadata, status changes."""
    run_a = await exec_store.get_run(run_id_a)
    if run_a is None:
        raise ValueError(f"Run '{run_id_a}' not found")

    run_b = await exec_store.get_run(run_id_b)
    if run_b is None:
        raise ValueError(f"Run '{run_id_b}' not found")

    records_a = await exec_store.list_records(run_id_a)
    records_b = await exec_store.list_records(run_id_b)

    by_task_a = {r.task_id: r for r in records_a}
    by_task_b = {r.task_id: r for r in records_b}

    all_tasks = sorted(set(by_task_a.keys()) | set(by_task_b.keys()))

    steps: list[dict[str, Any]] = []
    for task_id in all_tasks:
        step = await _compare_single_task(
            art_store, task_id, by_task_a.get(task_id), by_task_b.get(task_id)
        )
        steps.append(step)

    summary = _compute_summary(steps)

    return {
        "summary": summary,
        "run_a": run_id_a,
        "run_b": run_id_b,
        "workflow_a": run_a.workflow_name,
        "workflow_b": run_b.workflow_name,
        "status_a": run_a.status,
        "status_b": run_b.status,
        "steps": steps,
    }


async def _artifacts_differ(
    art_store: ArtifactStore,
    refs_a: list[str],
    refs_b: list[str],
) -> bool:
    """Check if artifact content differs between two sets of artifact refs."""
    if len(refs_a) != len(refs_b):
        return True

    for ref_a, ref_b in zip(sorted(refs_a), sorted(refs_b)):
        art_a = await art_store.get(ref_a)
        art_b = await art_store.get(ref_b)

        if art_a is None and art_b is None:
            continue
        if art_a is None or art_b is None:
            return True
        if art_a.content != art_b.content:
            return True

    return False


def format_diff(diff_result: dict[str, Any]) -> str:
    """Render a diff result as human-readable text."""
    lines: list[str] = []
    lines.append(f"Comparing: {diff_result['run_a']} vs {diff_result['run_b']}")
    lines.append(f"Workflow: {diff_result['workflow_a']}")
    lines.append(f"Status: {diff_result['status_a']} vs {diff_result['status_b']}")
    lines.append("")

    for step in diff_result["steps"]:
        _format_step_plain(step, lines)

    return "\n".join(lines)


def _format_step_plain(step: dict[str, Any], lines: list[str]) -> None:
    """Append plain-text lines for a single diff step."""
    task_id = step["task_id"]
    markers = _collect_step_markers(step)

    if markers:
        lines.append(f"  {task_id}:")
        for m in markers:
            lines.append(f"    {m}")
    else:
        lines.append(f"  {task_id}: (no changes)")


def _collect_step_markers(step: dict[str, Any]) -> list[str]:
    """Collect change markers for a diff step."""
    markers: list[str] = []
    if step["status_changed"]:
        markers.append(f"status: {step['status_a']} -> {step['status_b']}")
    if step["agent_changed"]:
        markers.append(f"agent: {step['agent_a']} -> {step['agent_b']}")
    if step["artifacts_changed"]:
        markers.append("artifacts: CHANGED")
    if step["latency_a"] is not None and step["latency_b"] is not None:
        delta = step["latency_b"] - step["latency_a"]
        sign = "+" if delta >= 0 else ""
        markers.append(
            f"latency: {step['latency_a']}ms -> {step['latency_b']}ms ({sign}{delta}ms)"
        )
    return markers
