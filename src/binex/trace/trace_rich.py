"""Rich-formatted trace timeline output."""

from __future__ import annotations

from typing import Any

from rich.panel import Panel
from rich.text import Text

from binex.cli.ui import STATUS_CONFIG, get_console, make_panel, make_table
from binex.stores.execution_store import ExecutionStore


async def format_trace_rich(store: ExecutionStore, run_id: str) -> None:
    """Print a rich-formatted timeline for a run directly to the terminal."""
    console = get_console()

    run = await store.get_run(run_id)
    records = await store.list_records(run_id)
    if not records:
        console.print(Text("No records found for this run.", style="red"))
        return

    records.sort(key=lambda r: r.timestamp)

    # Header
    if run:
        _, status_style = STATUS_CONFIG.get(run.status, (run.status, "dim"))
        console.print(make_panel(
            f"[bold]{run.workflow_name}[/bold]\n"
            f"Run: [cyan]{run.run_id}[/cyan]\n"
            f"Status: [{status_style}]{run.status}[/{status_style}]\n"
            f"Started: {run.started_at}"
            + (f"\nCompleted: {run.completed_at}" if run.completed_at else ""),
            title="Trace Timeline",
        ))

    # Timeline table
    table = make_table(
        ("#", {"style": "dim", "width": 3}),
        ("Node", {"style": "bold"}),
        ("Agent", {}),
        ("Status", {"justify": "center"}),
        ("Latency", {"justify": "right"}),
        ("Details", {}),
    )

    for i, rec in enumerate(records, 1):
        status = rec.status.value
        _, style = STATUS_CONFIG.get(status, ("unknown", "dim"))

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


async def format_trace_node_rich(record: Any) -> None:
    """Print a single node detail with rich directly to the terminal."""
    console = get_console()

    status = record.status.value
    _, style = STATUS_CONFIG.get(status, ("unknown", "dim"))
    # Extract base color for border
    color = style.split()[0]

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


async def format_trace_graph_rich(
    records: list,
    nodes: dict[str, str],
    edges: list[tuple[str, str]],
) -> None:
    """Print DAG as a rich table directly to the terminal."""
    console = get_console()

    rec_map = {r.task_id: r for r in records}

    # Build parent map (who depends on whom)
    parents: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        parents.setdefault(dst, []).append(src)

    # Topological sort
    order = _topo_sort(nodes, edges)

    table = make_table(
        ("#", {"style": "dim", "width": 3}),
        ("Node", {"style": "bold"}),
        ("Agent", {}),
        ("Status", {"justify": "center"}),
        ("Depends On", {}),
        title="DAG",
    )

    for i, node_id in enumerate(order, 1):
        rec = rec_map.get(node_id)
        if rec:
            status = rec.status.value
            _, style = STATUS_CONFIG.get(status, ("unknown", "dim"))
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
