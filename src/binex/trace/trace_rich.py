"""Rich-formatted trace timeline output."""

from __future__ import annotations

import io
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from binex.stores.execution_store import ExecutionStore

STATUS_STYLES = {
    "completed": ("green", "bold green"),
    "failed": ("red", "bold red"),
    "timed_out": ("yellow", "bold yellow"),
    "running": ("blue", "bold blue"),
    "skipped": ("dim", "dim"),
}


def _make_console() -> Console:
    """Create a Console that captures output without printing to terminal."""
    return Console(record=True, file=io.StringIO(), width=100)


async def format_trace_rich(store: ExecutionStore, run_id: str) -> str:
    """Generate a rich-formatted timeline for a run."""
    console = _make_console()

    run = await store.get_run(run_id)
    records = await store.list_records(run_id)
    if not records:
        console.print("[red]No records found for this run.[/red]")
        return console.export_text()

    records.sort(key=lambda r: r.timestamp)

    # Header
    if run:
        status_color = "green" if run.status == "completed" else "red"
        console.print(Panel(
            f"[bold]{run.workflow_name}[/bold]\n"
            f"Run: [cyan]{run.run_id}[/cyan]\n"
            f"Status: [{status_color}]{run.status}[/{status_color}]\n"
            f"Started: {run.started_at}"
            + (f"\nCompleted: {run.completed_at}" if run.completed_at else ""),
            title="[bold]Trace Timeline[/bold]",
            border_style="blue",
        ))

    # Timeline table
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Node", style="bold")
    table.add_column("Agent")
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right")
    table.add_column("Details")

    for i, rec in enumerate(records, 1):
        status = rec.status.value
        _color, style = STATUS_STYLES.get(status, ("white", "white"))

        details_parts = []
        if rec.input_artifact_refs:
            details_parts.append(f"in: {len(rec.input_artifact_refs)}")
        if rec.output_artifact_refs:
            details_parts.append(f"out: {len(rec.output_artifact_refs)}")
        if rec.error:
            details_parts.append(f"[red]{rec.error[:40]}[/red]")

        table.add_row(
            str(i),
            rec.task_id,
            rec.agent_id,
            Text(status, style=style),
            f"{rec.latency_ms}ms" if rec.latency_ms else "-",
            " | ".join(details_parts) if details_parts else "-",
        )

    console.print(table)
    return console.export_text()


async def format_trace_node_rich(record: Any) -> str:
    """Format a single node detail with rich."""
    console = _make_console()

    status = record.status.value
    color, style = STATUS_STYLES.get(status, ("white", "white"))

    lines = []
    lines.append(f"[bold]Node:[/bold] {record.task_id}")
    lines.append(f"[bold]Agent:[/bold] {record.agent_id}")
    lines.append(f"[bold]Status:[/bold] [{style}]{status}[/{style}]")
    lines.append(f"[bold]Latency:[/bold] {record.latency_ms}ms")
    lines.append(f"[bold]Timestamp:[/bold] {record.timestamp}")

    if record.model:
        lines.append(f"[bold]Model:[/bold] {record.model}")
    if record.input_artifact_refs:
        lines.append(
            f"[bold]Inputs:[/bold] {', '.join(record.input_artifact_refs)}"
        )
    if record.output_artifact_refs:
        lines.append(
            f"[bold]Outputs:[/bold] {', '.join(record.output_artifact_refs)}"
        )
    if record.prompt:
        lines.append(f"[bold]Prompt:[/bold] {record.prompt[:200]}")
    if record.error:
        lines.append(f"[bold red]Error:[/bold red] {record.error}")

    console.print(Panel(
        "\n".join(lines),
        title=f"[bold]{record.task_id}[/bold]",
        border_style=color,
    ))
    return console.export_text()


async def format_trace_graph_rich(
    records: list,
    nodes: dict[str, str],
    edges: list[tuple[str, str]],
) -> str:
    """Format DAG as a rich table with topological order and dependencies."""
    console = _make_console()

    rec_map = {r.task_id: r for r in records}

    # Build parent map (who depends on whom)
    parents: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        parents.setdefault(dst, []).append(src)

    # Topological sort
    order = _topo_sort(nodes, edges)

    table = Table(
        title="[bold blue]DAG[/bold blue]",
        show_header=True,
        header_style="bold",
        expand=True,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Node", style="bold")
    table.add_column("Agent")
    table.add_column("Status", justify="center")
    table.add_column("Depends On")

    for i, node_id in enumerate(order, 1):
        rec = rec_map.get(node_id)
        if rec:
            status = rec.status.value
            _color, style = STATUS_STYLES.get(status, ("white", "white"))
            agent = rec.agent_id
        else:
            status = "-"
            style = "dim"
            agent = "-"

        deps = parents.get(node_id, [])
        deps_str = ", ".join(deps) if deps else "-"

        table.add_row(
            str(i),
            node_id,
            agent,
            Text(status, style=style),
            deps_str,
        )

    console.print(table)
    return console.export_text()


def _topo_sort(
    nodes: dict[str, str],
    edges: list[tuple[str, str]],
) -> list[str]:
    """Kahn's algorithm for topological sort."""
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    children: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        in_degree.setdefault(dst, 0)
        in_degree[dst] += 1
        children.setdefault(src, []).append(dst)

    queue = [n for n in nodes if in_degree.get(n, 0) == 0]
    result: list[str] = []
    while queue:
        queue.sort()
        node = queue.pop(0)
        result.append(node)
        for child in children.get(node, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    return result
