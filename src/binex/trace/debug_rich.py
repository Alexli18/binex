"""Rich-formatted debug report output (optional dependency)."""

from __future__ import annotations

from io import StringIO

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from binex.trace.debug_report import DebugReport, _truncate

STATUS_COLORS = {
    "completed": "green",
    "failed": "red",
    "timed_out": "yellow",
    "skipped": "dim",
}


def format_debug_report_rich(
    report: DebugReport,
    *,
    node_filter: str | None = None,
    errors_only: bool = False,
) -> str:
    """Format a debug report with rich colors. Returns a string."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)

    # Header
    status_color = STATUS_COLORS.get(report.status, "white")
    header = Text()
    header.append(f"Debug: {report.run_id}\n", style="bold")
    header.append(f"Workflow: {report.workflow_name}\n")
    header.append("Status:   ")
    header.append(report.status, style=f"bold {status_color}")
    header.append(f" ({report.completed_nodes}/{report.total_nodes} completed)\n")
    header.append(f"Duration: {report.duration_ms / 1000}s")
    console.print(Panel(header, title="Debug Report"))

    # Filter nodes
    nodes = report.nodes
    if node_filter:
        nodes = [n for n in nodes if n.node_id == node_filter]
    if errors_only:
        nodes = [n for n in nodes if n.status in ("failed", "timed_out")]

    for node in nodes:
        color = STATUS_COLORS.get(node.status, "white")
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

            # Render output content as Markdown
            for art in node.output_artifacts:
                content_str = art.content if art.content is not None else ""
                if not isinstance(content_str, str):
                    import json
                    content_str = json.dumps(content_str, default=str, indent=2)
                if content_str:
                    parts.append(Markdown(content_str))

        console.print(Panel(Group(*parts), title=title, border_style=color))

    return buf.getvalue()


__all__ = ["format_debug_report_rich"]
