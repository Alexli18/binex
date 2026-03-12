"""Debug report model and builder for post-mortem workflow inspection."""

from __future__ import annotations

from dataclasses import dataclass, field

from binex.models.artifact import Artifact
from binex.models.task import TaskStatus


@dataclass
class NodeReport:
    """Debug information for a single workflow node."""

    node_id: str
    agent_id: str
    status: str
    latency_ms: int = 0
    prompt: str | None = None
    model: str | None = None
    error: str | None = None
    input_artifacts: list[Artifact] = field(default_factory=list)
    output_artifacts: list[Artifact] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)


@dataclass
class DebugReport:
    """Complete post-mortem view of a workflow run."""

    run_id: str
    workflow_name: str
    status: str
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    duration_ms: int
    nodes: list[NodeReport] = field(default_factory=list)


def _build_node_reports(
    records: list,
    art_index: dict[str, Artifact],
) -> tuple[list[NodeReport], list[str]]:
    """Build NodeReport list from execution records.

    Returns a tuple of (node_reports, failed_node_ids).
    """
    nodes: list[NodeReport] = []
    failed_node_ids: list[str] = []
    for rec in records:
        input_arts = [art_index[ref] for ref in rec.input_artifact_refs if ref in art_index]
        output_arts = [art_index[ref] for ref in rec.output_artifact_refs if ref in art_index]

        status_str = rec.status.value if isinstance(rec.status, TaskStatus) else str(rec.status)

        node = NodeReport(
            node_id=rec.task_id,
            agent_id=rec.agent_id,
            status=status_str,
            latency_ms=rec.latency_ms,
            prompt=rec.prompt,
            model=rec.model,
            error=rec.error,
            input_artifacts=input_arts,
            output_artifacts=output_arts,
        )
        nodes.append(node)

        if rec.status in (TaskStatus.FAILED, TaskStatus.TIMED_OUT):
            failed_node_ids.append(rec.task_id)

    return nodes, failed_node_ids


def _infer_skipped_nodes(
    recorded_count: int,
    total_nodes: int,
    failed_ids: list[str],
) -> list[NodeReport]:
    """Infer skipped nodes from the difference between total and recorded counts."""
    skipped_count = max(0, total_nodes - recorded_count)
    return [
        NodeReport(
            node_id=f"<skipped-{i + 1}>",
            agent_id="",
            status="skipped",
            blocked_by=list(failed_ids),
        )
        for i in range(skipped_count)
    ]


async def build_debug_report(
    exec_store,
    art_store,
    run_id: str,
) -> DebugReport | None:
    """Build a debug report from execution and artifact stores.

    Returns None if the run_id does not exist.
    """
    run = await exec_store.get_run(run_id)
    if run is None:
        return None

    records = await exec_store.list_records(run_id)
    artifacts = await art_store.list_by_run(run_id)
    art_index: dict[str, Artifact] = {a.id: a for a in artifacts}

    # Compute duration
    duration_ms = 0
    if run.started_at and run.completed_at:
        delta = run.completed_at - run.started_at
        duration_ms = int(delta.total_seconds() * 1000)

    nodes, failed_node_ids = _build_node_reports(records, art_index)
    nodes.extend(_infer_skipped_nodes(len(records), run.total_nodes, failed_node_ids))

    return DebugReport(
        run_id=run.run_id,
        workflow_name=run.workflow_name,
        status=run.status,
        total_nodes=run.total_nodes,
        completed_nodes=run.completed_nodes,
        failed_nodes=run.failed_nodes,
        duration_ms=duration_ms,
        nodes=nodes,
    )


def _truncate(content: str, max_len: int = 500) -> str:
    """Truncate content to max_len characters with ellipsis."""
    if len(content) <= max_len:
        return content
    return content[:max_len] + "..."


def format_debug_report(
    report: DebugReport,
    *,
    node_filter: str | None = None,
    errors_only: bool = False,
) -> str:
    """Format a debug report as plain text."""
    lines: list[str] = []

    # Header
    lines.append(f"=== Debug: {report.run_id} ===")
    lines.append(f"Workflow: {report.workflow_name}")
    lines.append(
        f"Status:   {report.status} ({report.completed_nodes}/{report.total_nodes} completed)"
    )
    duration_s = report.duration_ms / 1000
    lines.append(f"Duration: {duration_s}s")
    lines.append("")

    nodes = _filter_nodes(report.nodes, node_filter, errors_only)

    for node in nodes:
        _format_node_plain(node, lines)

    return "\n".join(lines)


def _filter_nodes(
    nodes: list[NodeReport],
    node_filter: str | None,
    errors_only: bool,
) -> list[NodeReport]:
    """Apply node_filter and errors_only filters."""
    if node_filter:
        nodes = [n for n in nodes if n.node_id == node_filter]
    if errors_only:
        nodes = [n for n in nodes if n.status in ("failed", "timed_out")]
    return nodes


def _format_active_node_plain(node: NodeReport, lines: list[str]) -> None:
    """Append detail lines for a non-skipped node."""
    lines.append(f"  Agent:  {node.agent_id}")
    if node.prompt:
        lines.append(f"  Prompt: {_truncate(node.prompt)}")
    for art in node.input_artifacts:
        lines.append(f"  Input:  {art.id} <- {art.lineage.produced_by}")
    for art in node.output_artifacts:
        content_str = _truncate(str(art.content)) if art.content else ""
        lines.append(f"  Output: {art.id} ({art.type})")
        if content_str:
            lines.append(f"          {content_str}")
    if node.error:
        lines.append(f"  ERROR:  {node.error}")


def _format_node_plain(node: NodeReport, lines: list[str]) -> None:
    """Append plain-text lines for a single node report."""
    latency_str = f" {node.latency_ms}ms" if node.latency_ms else ""
    lines.append(f"-- {node.node_id} [{node.status}]{latency_str} ------")

    if node.status == "skipped":
        if node.blocked_by:
            lines.append(f"  Blocked by: {', '.join(node.blocked_by)}")
    else:
        _format_active_node_plain(node, lines)

    lines.append("")


def format_debug_report_json(report: DebugReport) -> dict:
    """Format a debug report as a JSON-serializable dict."""
    return {
        "run_id": report.run_id,
        "workflow_name": report.workflow_name,
        "status": report.status,
        "total_nodes": report.total_nodes,
        "completed_nodes": report.completed_nodes,
        "failed_nodes": report.failed_nodes,
        "duration_ms": report.duration_ms,
        "nodes": [
            {
                "node_id": n.node_id,
                "agent_id": n.agent_id,
                "status": n.status,
                "latency_ms": n.latency_ms,
                "prompt": n.prompt,
                "model": n.model,
                "error": n.error,
                "blocked_by": n.blocked_by,
                "input_artifacts": [a.id for a in n.input_artifacts],
                "output_artifacts": [
                    {
                        "id": a.id,
                        "type": a.type,
                        "content": _truncate(str(a.content)) if a.content else None,
                    }
                    for a in n.output_artifacts
                ],
            }
            for n in report.nodes
        ],
    }


__all__ = [
    "DebugReport",
    "NodeReport",
    "build_debug_report",
    "format_debug_report",
    "format_debug_report_json",
]
