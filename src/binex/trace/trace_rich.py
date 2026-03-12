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
    ctx = _GraphContext()

    console.print("[bold]DAG[/bold]")
    console.print()

    for node_id in order:
        rec = rec_map.get(node_id)
        status = rec.status.value if rec else "pending"
        latency = rec.latency_ms if rec else None
        icon, color = _STATUS_STYLES.get(status, ("?", "dim"))
        node_parents = parents_map.get(node_id, [])
        node_children = children_map.get(node_id, [])

        lane = ctx.assign_lane(node_id, node_parents)
        ctx.active[lane] = node_id if node_children else None

        _render_merge_line(console, ctx, node_id, node_parents, lane)
        _render_node_line(console, ctx, node_id, lane, color, icon, status, latency)
        _render_fork_or_cont(console, ctx, node_id, node_children, lane)

    console.print()


_STATUS_STYLES: dict[str, tuple[str, str]] = {
    "completed": ("\u2713", "green"),
    "failed": ("\u2717", "red"),
    "cancelled": ("-", "dim"),
    "running": ("\u25cb", "yellow"),
    "pending": ("\u25cb", "dim"),
}


class _GraphContext:
    """Mutable state for DAG graph rendering: lane assignments and active lanes."""

    def __init__(self) -> None:
        self.lanes: dict[str, int] = {}
        self.active: list[str | None] = []

    def alloc(self) -> int:
        for i, v in enumerate(self.active):
            if v is None:
                return i
        self.active.append(None)
        return len(self.active) - 1

    def ensure(self, lane: int) -> None:
        while len(self.active) <= lane:
            self.active.append(None)

    def assign_lane(self, node_id: str, node_parents: list[str]) -> int:
        if len(node_parents) > 1:
            parent_lanes = [self.lanes[p] for p in node_parents if p in self.lanes]
            lane = min(parent_lanes) if parent_lanes else self.lanes.get(node_id, self.alloc())
        elif node_id in self.lanes:
            lane = self.lanes[node_id]
        elif node_parents:
            lane = self.lanes.get(node_parents[0], 0)
        else:
            lane = self.alloc()
        self.lanes[node_id] = lane
        self.ensure(lane)
        return lane


def _format_latency(ms: int | None) -> str:
    if ms is None or ms == 0:
        return ""
    if ms >= 10000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"


def _build_lane_prefix(ctx: _GraphContext, left: int) -> str:
    """Build prefix string for columns before the left edge of a connector."""
    before: list[str] = []
    for col in range(left):
        if col < len(ctx.active) and ctx.active[col] is not None:
            before.append("\u2502")
        else:
            before.append(" ")
    return " ".join(before) + " " if before else ""


def _build_hline_segment(
    left: int, right: int, specials: set[int],
    left_ch: str, right_ch: str, mid_ch: str,
) -> str:
    """Build the horizontal segment between left and right columns."""
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
        if col < right:
            seg += "\u2500"
    return seg


def _build_lane_suffix(ctx: _GraphContext, right: int) -> str:
    """Build suffix string for columns after the right edge of a connector."""
    after: list[str] = []
    for col in range(right + 1, len(ctx.active)):
        if ctx.active[col] is not None:
            after.append("\u2502")
        else:
            after.append(" ")
    return " " + " ".join(after) if after else ""


def _render_hline(
    console, ctx: _GraphContext,
    left: int, right: int, specials: set[int],
    left_ch: str, right_ch: str, mid_ch: str,
) -> None:
    """Render a horizontal connector line (fork or merge)."""
    prefix = _build_lane_prefix(ctx, left)
    seg = _build_hline_segment(left, right, specials, left_ch, right_ch, mid_ch)
    suffix = _build_lane_suffix(ctx, right)
    console.print("  " + prefix + seg + suffix)


def _render_cont(console, ctx: _GraphContext) -> None:
    """Render continuation lines between nodes."""
    parts: list[str] = []
    for col in range(len(ctx.active)):
        parts.append("\u2502" if ctx.active[col] is not None else " ")
    line = _space_cols(parts).rstrip()
    if line.strip():
        console.print("  " + line)


def _render_merge_line(
    console, ctx: _GraphContext,
    node_id: str, node_parents: list[str], lane: int,
) -> None:
    """Render merge connector if node has multiple parents."""
    if len(node_parents) <= 1:
        return
    merge_lanes = sorted({ctx.lanes[p] for p in node_parents if p in ctx.lanes})
    if len(merge_lanes) <= 1:
        return
    _render_hline(
        console, ctx,
        merge_lanes[0], merge_lanes[-1],
        set(merge_lanes),
        "\u251c", "\u2518", "\u2534",
    )
    for p in node_parents:
        pl = ctx.lanes.get(p, -1)
        if pl != lane and 0 <= pl < len(ctx.active):
            ctx.active[pl] = None


def _render_node_line(
    console, ctx: _GraphContext,
    node_id: str, lane: int,
    color: str, icon: str, status: str, latency: int | None,
) -> None:
    """Render the main node line with status and latency."""
    lat_str = _format_latency(latency)
    if lat_str:
        lat_str = f"  {lat_str}"

    parts: list[str] = []
    for col in range(len(ctx.active)):
        if col == lane:
            parts.append(f"[{color}]\u25cf[/{color}]")
        elif ctx.active[col] is not None:
            parts.append("\u2502")
        else:
            parts.append(" ")
    while parts and parts[-1] == " ":
        parts.pop()
    console.print(
        f"  {_space_cols(parts)} "
        f"[bold]{node_id:<14}[/bold] "
        f"[{color}]{icon} {status:<10}[/{color}]"
        f"[dim]{lat_str}[/dim]",
    )


def _render_fork_or_cont(
    console, ctx: _GraphContext,
    node_id: str, node_children: list[str], lane: int,
) -> None:
    """Render fork connector, single-child continuation, or leaf termination."""
    if len(node_children) > 1:
        sorted_children = sorted(node_children)
        child_lanes = [lane]
        if sorted_children[0] not in ctx.lanes:
            ctx.lanes[sorted_children[0]] = lane
        for child in sorted_children[1:]:
            if child not in ctx.lanes:
                cl = ctx.alloc()
                ctx.ensure(cl)
                ctx.active[cl] = child
                ctx.lanes[child] = cl
                child_lanes.append(cl)
            else:
                child_lanes.append(ctx.lanes[child])
        child_lanes_sorted = sorted(child_lanes)
        _render_hline(
            console, ctx,
            child_lanes_sorted[0], child_lanes_sorted[-1],
            set(child_lanes),
            "\u251c", "\u2510", "\u252c",
        )
    elif len(node_children) == 1:
        child = node_children[0]
        if child not in ctx.lanes:
            ctx.lanes[child] = lane
            ctx.ensure(lane)
            ctx.active[lane] = child
        _render_cont(console, ctx)
    else:
        ctx.active[lane] = None
        _render_cont(console, ctx)


def _space_cols(parts: list[str]) -> str:
    """Join lane columns with single space."""
    return " ".join(parts)


def _topo_sort(
    nodes: dict[str, str],
    edges: list[tuple[str, str]],
) -> list[str]:
    """Kahn's algorithm for topological sort.

    NOTE: This duplicates the algorithm in ``DAG.topological_order()``
    (src/binex/graph/dag.py).  A direct replacement is impractical because
    DAG requires forward/backward adjacency sets and a node ``set[str]``,
    whereas this call-site works with a label dict and an edge list.
    Building a DAG just to sort would add complexity without benefit.
    """
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
