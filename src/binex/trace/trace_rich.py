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
    """Print DAG as git-style graph with rich colors."""
    console = get_console()
    rec_map = {r.task_id: r for r in records}

    # Build parent/children maps
    children_map: dict[str, list[str]] = {n: [] for n in nodes}
    parents_map: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        children_map.setdefault(src, []).append(dst)
        parents_map.setdefault(dst, []).append(src)

    order = _topo_sort(nodes, edges)

    # Assign lanes: track which lane each node occupies
    lanes: dict[str, int] = {}  # node_id -> lane index
    active_lanes: list[str | None] = []  # lane index -> node_id or None

    def _alloc_lane() -> int:
        """Find first free lane or create new one."""
        for i, occupant in enumerate(active_lanes):
            if occupant is None:
                return i
        active_lanes.append(None)
        return len(active_lanes) - 1

    def _free_lane(lane: int) -> None:
        active_lanes[lane] = None

    # Status display helpers
    status_icons: dict[str, tuple[str, str]] = {
        "completed": ("\u2713", "green"),
        "failed": ("\u2717", "red"),
        "cancelled": ("-", "dim"),
        "running": ("\u25cb", "yellow"),
        "pending": ("\u25cb", "dim"),
    }

    def _format_latency(ms: int | None) -> str:
        if ms is None or ms == 0:
            return ""
        if ms >= 10000:
            return f"{ms / 1000:.1f}s"
        return f"{ms}ms"

    console.print("[bold]DAG[/bold]")
    console.print()

    for node_id in order:
        rec = rec_map.get(node_id)
        status = rec.status.value if rec else "pending"
        latency = rec.latency_ms if rec else None
        icon, color = status_icons.get(status, ("?", "dim"))

        node_parents = parents_map.get(node_id, [])
        node_children = children_map.get(node_id, [])

        # Determine this node's lane
        if node_parents:
            first_parent_lane = lanes.get(node_parents[0], 0)
            lane = first_parent_lane
        else:
            lane = _alloc_lane()

        lanes[node_id] = lane
        # Keep lane active only if this node has children
        if lane < len(active_lanes):
            active_lanes[lane] = node_id if node_children else None
        else:
            while len(active_lanes) <= lane:
                active_lanes.append(None)
            active_lanes[lane] = node_id if node_children else None

        # --- Merge lines (if multiple parents) ---
        if len(node_parents) > 1:
            merge_lanes = sorted(
                lanes.get(p, 0) for p in node_parents
            )
            min_lane = min(merge_lanes)
            max_lane = max(merge_lanes)

            line = ""
            num_cols = max(len(active_lanes), max_lane + 1)
            for col in range(num_cols):
                if col == min_lane:
                    line += "\u251c"  # ├
                elif col == max_lane:
                    line += "\u2518"  # ┘
                elif min_lane < col < max_lane:
                    if col in merge_lanes:
                        line += "\u2534"  # ┴
                    else:
                        line += "\u2500"  # ─
                elif col < len(active_lanes) and active_lanes[col] is not None:
                    line += "\u2502"  # │
                else:
                    line += " "
            console.print(f"  {_expand_lanes(line)}")

            # Free merged parent lanes (except the node's own lane)
            for p in node_parents:
                p_lane = lanes.get(p, -1)
                if p_lane != lane and 0 <= p_lane < len(active_lanes):
                    _free_lane(p_lane)

        # --- Node line ---
        lat_str = _format_latency(latency)
        if lat_str:
            lat_str = f"  {lat_str}"

        line_parts: list[str] = []
        for col in range(len(active_lanes)):
            if col == lane:
                line_parts.append(f"[{color}]\u25cf[/{color}]")
            elif active_lanes[col] is not None:
                line_parts.append("\u2502")
            else:
                line_parts.append(" ")

        node_text = " ".join(line_parts)
        console.print(
            f"  {node_text} "
            f"[bold]{node_id:<14}[/bold] "
            f"[{color}]{icon} {status:<10}[/{color}]"
            f"[dim]{lat_str}[/dim]"
        )

        # --- Fork lines (if multiple children) ---
        if len(node_children) > 1:
            child_lanes = [lane]  # first child inherits parent lane
            for child in node_children[1:]:
                cl = _alloc_lane()
                while len(active_lanes) <= cl:
                    active_lanes.append(None)
                active_lanes[cl] = child
                lanes[child] = cl
                child_lanes.append(cl)

            min_lane = min(child_lanes)
            max_lane = max(child_lanes)

            line = ""
            for col in range(len(active_lanes)):
                if col == min_lane:
                    line += "\u251c"  # ├
                elif col == max_lane:
                    line += "\u2510"  # ┐
                elif min_lane < col < max_lane:
                    if col in child_lanes:
                        line += "\u252c"  # ┬
                    else:
                        line += "\u2500"  # ─
                elif active_lanes[col] is not None:
                    line += "\u2502"  # │
                else:
                    line += " "
            console.print(f"  {_expand_lanes(line)}")
        else:
            # Continuation lines
            if node_children:
                child = node_children[0]
                if child not in lanes:
                    lanes[child] = lane
                    if lane < len(active_lanes):
                        active_lanes[lane] = child
                    else:
                        while len(active_lanes) <= lane:
                            active_lanes.append(None)
                        active_lanes[lane] = child

            cont_parts: list[str] = []
            for col in range(len(active_lanes)):
                if active_lanes[col] is not None:
                    cont_parts.append("\u2502")
                else:
                    cont_parts.append(" ")
            cont_line = " ".join(cont_parts).rstrip()
            if cont_line.strip():
                console.print(f"  {cont_line}")

    console.print()


def _expand_lanes(line: str) -> str:
    """Expand single-char lane columns to spaced format."""
    return " ".join(line)


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
