"""Rich-formatted debug report output (optional dependency)."""

from __future__ import annotations

from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from binex.cli.ui import STATUS_CONFIG, make_panel, render_to_string
from binex.trace.debug_report import DebugReport, _truncate


def format_debug_report_rich(
    report: DebugReport,
    *,
    node_filter: str | None = None,
    errors_only: bool = False,
) -> str:
    """Format a debug report with rich colors. Returns a string."""
    from binex.trace.debug_report import _filter_nodes

    # Header
    _, status_style = STATUS_CONFIG.get(report.status, (report.status, "dim"))
    header = Text()
    header.append(f"Debug: {report.run_id}\n", style="bold")
    header.append(f"Workflow: {report.workflow_name}\n")
    header.append("Status:   ")
    header.append(report.status, style=f"bold {status_style}")
    header.append(f" ({report.completed_nodes}/{report.total_nodes} completed)\n")
    header.append(f"Duration: {report.duration_ms / 1000}s")

    parts = [make_panel(header, title="Debug Report")]

    nodes = _filter_nodes(report.nodes, node_filter, errors_only)
    for node in nodes:
        parts.append(_render_node_rich(node))

    return render_to_string(Group(*parts))


def _render_node_rich(node) -> Panel:
    """Render a single node as a rich Panel."""
    _, style = STATUS_CONFIG.get(node.status, (node.status, "dim"))
    # Extract base color from style (e.g. "red bold" -> "red", "dim" -> "dim")
    color = style.split()[0]
    title = f"{node.node_id} [{node.status}]"
    if node.latency_ms:
        title += f" {node.latency_ms}ms"

    parts: list[Text | Markdown] = []
    meta = Text()
    if node.status == "skipped":
        if node.blocked_by:
            meta.append(f"  Blocked by: {', '.join(node.blocked_by)}", style="dim")
        parts.append(meta)
    else:
        meta.append(f"  Agent:  {node.agent_id}\n")
        if node.prompt:
            meta.append(f"  Prompt: {_truncate(node.prompt)}\n")
        for art in node.input_artifacts:
            meta.append(f"  Input:  {art.id} <- {art.lineage.produced_by}\n")
        for art in node.output_artifacts:
            meta.append(f"  Output: {art.id} ({art.type})\n")
        if node.error:
            meta.append(f"  ERROR:  {node.error}", style="bold red")
        parts.append(meta)

        for art in node.output_artifacts:
            content_str = art.content if art.content is not None else ""
            if not isinstance(content_str, str):
                import json
                content_str = json.dumps(content_str, default=str, indent=2)
            if content_str:
                parts.append(Markdown(content_str))

    return Panel(Group(*parts), title=title, border_style=color)


__all__ = ["format_debug_report_rich"]
