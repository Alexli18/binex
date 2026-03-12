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

    children_map: dict[str, list[str]] = {n: [] for n in nodes}
    parents_map: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        children_map.setdefault(src, []).append(dst)
        parents_map.setdefault(dst, []).append(src)

    order = _topo_sort(nodes, edges)

    lanes: dict[str, int] = {}
    active: list[str | None] = []  # lane -> node_id or None

    def _alloc() -> int:
        for i, v in enumerate(active):
            if v is None:
                return i
        active.append(None)
        return len(active) - 1

    def _ensure(lane: int) -> None:
        while len(active) <= lane:
            active.append(None)

    status_styles: dict[str, tuple[str, str]] = {
        "completed": ("\u2713", "green"),
        "failed": ("\u2717", "red"),
        "cancelled": ("-", "dim"),
        "running": ("\u25cb", "yellow"),
        "pending": ("\u25cb", "dim"),
    }

    def _lat(ms: int | None) -> str:
        if ms is None or ms == 0:
            return ""
        if ms >= 10000:
            return f"{ms / 1000:.1f}s"
        return f"{ms}ms"

    def _render_hline(
        left: int, right: int, specials: set[int],
        left_ch: str, right_ch: str, mid_ch: str,
    ) -> None:
        """Render a horizontal connector line (fork or merge).

        Between left and right, use ─ as filler (no spaces).
        Outside that range, use normal spaced columns.
        """
        before: list[str] = []
        for col in range(left):
            if col < len(active) and active[col] is not None:
                before.append("\u2502")
            else:
                before.append(" ")
        prefix = " ".join(before) + " " if before else ""

        # The horizontal segment: no spaces between chars
        seg = ""
        for col in range(left, right + 1):
            if col == left:
                seg += left_ch
            elif col == right:
                seg += right_ch
            elif col in specials:
                seg += mid_ch
            else:
                seg += "\u2500"

        after: list[str] = []
        for col in range(right + 1, len(active)):
            if active[col] is not None:
                after.append("\u2502")
            else:
                after.append(" ")
        suffix = " " + " ".join(after) if after else ""

        console.print("  " + prefix + seg + suffix)

    def _render_cont() -> None:
        """Render continuation lines between nodes."""
        parts: list[str] = []
        for col in range(len(active)):
            if active[col] is not None:
                parts.append("\u2502")
            else:
                parts.append(" ")
        line = _space_cols(parts).rstrip()
        if line.strip():
            console.print("  " + line)

    def _max_col() -> int:
        return len(active)

    console.print("[bold]DAG[/bold]")
    console.print()

    for node_id in order:
        rec = rec_map.get(node_id)
        status = rec.status.value if rec else "pending"
        latency = rec.latency_ms if rec else None
        icon, color = status_styles.get(status, ("?", "dim"))
        node_parents = parents_map.get(node_id, [])
        node_children = children_map.get(node_id, [])

        # Assign lane: inherit from first parent, or allocate
        if node_id in lanes:
            lane = lanes[node_id]
        elif node_parents:
            lane = lanes.get(node_parents[0], 0)
        else:
            lane = _alloc()
        lanes[node_id] = lane
        _ensure(lane)
        active[lane] = node_id if node_children else None

        # --- Merge line ---
        if len(node_parents) > 1:
            merge_lanes = sorted(
                {lanes[p] for p in node_parents if p in lanes},
            )
            if len(merge_lanes) > 1:
                _render_hline(
                    merge_lanes[0], merge_lanes[-1],
                    set(merge_lanes),
                    "\u251c", "\u2518", "\u2534",  # ├ ┘ ┴
                )
                # Free merged lanes
                for p in node_parents:
                    pl = lanes.get(p, -1)
                    if pl != lane and 0 <= pl < len(active):
                        active[pl] = None

        # --- Node line ---
        lat_str = _lat(latency)
        if lat_str:
            lat_str = f"  {lat_str}"

        parts: list[str] = []
        for col in range(len(active)):
            if col == lane:
                parts.append(f"[{color}]\u25cf[/{color}]")
            elif active[col] is not None:
                parts.append("\u2502")
            else:
                parts.append(" ")
        console.print(
            f"  {_space_cols(parts)} "
            f"[bold]{node_id:<14}[/bold] "
            f"[{color}]{icon} {status:<10}[/{color}]"
            f"[dim]{lat_str}[/dim]",
        )

        # --- Fork line ---
        if len(node_children) > 1:
            child_lanes = [lane]
            for child in node_children[1:]:
                cl = _alloc()
                _ensure(cl)
                active[cl] = child
                lanes[child] = cl
                child_lanes.append(cl)
            child_lanes_sorted = sorted(child_lanes)
            _render_hline(
                child_lanes_sorted[0], child_lanes_sorted[-1],
                set(child_lanes),
                "\u251c", "\u2510", "\u252c",  # ├ ┐ ┬
            )
        elif len(node_children) == 1:
            child = node_children[0]
            if child not in lanes:
                lanes[child] = lane
                _ensure(lane)
                active[lane] = child
            _render_cont()
        else:
            # Leaf node — free lane, show cont if others active
            active[lane] = None
            _render_cont()

    console.print()


def _space_cols(parts: list[str]) -> str:
    """Join lane columns with single space."""
    return " ".join(parts)


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
