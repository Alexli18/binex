"""CLI `binex explore` command — interactive dashboard for runs."""

from __future__ import annotations

import asyncio
import json

import click

from binex.cli import get_stores, has_rich
from binex.trace.lineage import build_lineage_tree, format_lineage_tree


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _short_id(run_id: str) -> str:
    """Shorten run ID for display."""
    return run_id[:16] if len(run_id) > 16 else run_id


def _time_ago(dt) -> str:
    """Human-readable relative time."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"



def _preview(content, max_len: int = 50) -> str:
    """Truncate content for preview."""
    if content is None:
        return "(empty)"
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


@click.command("explore", epilog="""\b
Examples:
  binex explore              Browse recent runs → interactive dashboard
  binex explore <run_id>     Jump directly to the dashboard for a run
""")
@click.argument("run_id", required=False, default=None)
def explore_cmd(run_id: str | None) -> None:
    """Interactive dashboard for runs, traces, and artifacts."""
    try:
        asyncio.run(_explore(run_id))
    except KeyboardInterrupt:
        click.echo("\nBye.")


async def _explore(run_id: str | None) -> None:
    exec_store, art_store = _get_stores()
    try:
        if run_id:
            run = await exec_store.get_run(run_id)
            if run is None:
                click.echo(f"Run '{run_id}' not found.")
                click.echo("Tip: use 'binex explore' to browse available runs.")
                return
            await _dashboard(exec_store, art_store, run_id)
        else:
            await _browse_runs(exec_store, art_store)
    finally:
        await exec_store.close()


async def _browse_runs(exec_store, art_store) -> None:
    """List recent runs and let user pick one for the dashboard."""
    runs = await exec_store.list_runs()
    if not runs:
        click.echo("No runs found. Run a workflow first:")
        click.echo("  binex run examples/simple.yaml --var input=\"hello\"")
        return

    runs.sort(key=lambda r: r.started_at, reverse=True)
    runs = runs[:20]

    click.echo()

    if has_rich():
        from binex.cli.ui import get_console, make_table, status_text

        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Run ID", {"style": "cyan", "min_width": 16}),
            ("Workflow", {"min_width": 20}),
            ("Status", {"min_width": 10}),
            ("Nodes", {"justify": "center", "min_width": 6}),
            ("Cost", {"justify": "right", "min_width": 8}),
            ("When", {"style": "dim", "min_width": 8}),
            title="Recent Runs",
        )

        for i, run in enumerate(runs, 1):
            nodes = f"{run.completed_nodes}/{run.total_nodes}"
            cost_str = f"${run.total_cost:.2f}" if run.total_cost else ""
            table.add_row(
                str(i),
                _short_id(run.run_id),
                run.workflow_name,
                status_text(run.status),
                nodes,
                cost_str,
                _time_ago(run.started_at),
            )
        get_console().print(table)
    else:
        click.echo("  Recent runs:")
        click.echo()
        from binex.cli.ui import STATUS_CONFIG
        for i, run in enumerate(runs, 1):
            display, _ = STATUS_CONFIG.get(run.status, (run.status, "dim"))
            ago = _time_ago(run.started_at)
            click.echo(
                f"  {i:>3})  {_short_id(run.run_id):<18} "
                f"{run.workflow_name:<25} {display:<12} {ago}"
            )

    click.echo()

    while True:
        choice = click.prompt(
            "  Select run (or q to quit)", default="1",
        )
        if choice.lower() == "q":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(runs):
                await _dashboard(exec_store, art_store, runs[idx].run_id)
                return
        except ValueError:
            pass
        click.echo(f"  Invalid choice. Enter 1-{len(runs)} or q.")


async def _dashboard(exec_store, art_store, run_id: str) -> None:
    """Core dashboard: render summary + node table, then action menu loop."""
    while True:
        run = await exec_store.get_run(run_id)
        if run is None:
            click.echo(f"Run '{run_id}' not found.")
            return
        records = await exec_store.list_records(run_id)
        cost_records = await exec_store.list_costs(run_id)

        click.echo()
        _render_dashboard(run, records, run_id, cost_records)
        _print_dashboard_menu()

        choice = click.prompt("  Action", default="q")
        key = choice.strip().lower()

        if key == "q":
            return
        elif key == "t":
            await _action_trace(exec_store, run_id)
        elif key == "g":
            await _action_graph(exec_store, run_id)
        elif key == "d":
            await _action_debug(exec_store, art_store, run_id)
        elif key == "c":
            await _action_cost(exec_store, run_id)
        elif key == "a":
            await _action_artifacts(exec_store, art_store, run_id)
        elif key == "n":
            node_arts = await _action_node(exec_store, art_store, run_id, records)
            if node_arts:
                if _wait_for_enter_or_preview(node_arts):
                    return
                continue
        elif key == "r":
            new_run_id = await _action_replay(exec_store, art_store, run_id, run, records)
            if new_run_id:
                choice = click.prompt(
                    "  [Enter] back · [e] explore new run · [q] quit",
                    default="",
                )
                k = choice.strip().lower()
                if k == "q":
                    return
                if k == "e":
                    run_id = new_run_id
                continue
        else:
            click.echo("  Unknown action. Use t/g/d/c/a/n/r/q.")
            continue

        if _wait_for_enter():
            return


def _render_dashboard(run, records, run_id: str, cost_records=None) -> None:
    """Render dashboard panel with header, status, and node table."""
    # Build per-node cost lookup
    node_costs: dict[str, float] = {}
    for cr in (cost_records or []):
        node_costs[cr.task_id] = node_costs.get(cr.task_id, 0.0) + cr.cost

    if has_rich():
        from rich.console import Group as RichGroup
        from rich.text import Text

        from binex.cli.ui import (
            STATUS_CONFIG,
            get_console,
            make_header,
            make_panel,
            make_table,
            status_text,
        )

        header = make_header(run=_short_id(run_id), workflow=run.workflow_name)

        # Status line
        _, st_style = STATUS_CONFIG.get(run.status, (run.status, "dim"))
        status_line = Text()
        status_line.append("Status: ", style="dim")
        status_line.append(run.status, style=st_style)
        status_line.append(
            f"  ·  Nodes: {run.completed_nodes}/{run.total_nodes}", style="dim",
        )
        if run.total_cost:
            status_line.append(f"  ·  Cost: ${run.total_cost:.4f}", style="cyan")
        status_line.append(f"  ·  {_time_ago(run.started_at)}", style="dim")

        # Node table
        table = make_table(
            ("Node", {"style": "bold", "min_width": 14}),
            ("Status", {"min_width": 10}),
            ("Agent", {"style": "dim"}),
            ("Cost", {"justify": "right"}),
            ("Latency", {"justify": "right"}),
        )
        for rec in records:
            latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
            nc = node_costs.get(rec.task_id)
            cost_str = f"${nc:.4f}" if nc else ""
            table.add_row(
                rec.task_id,
                status_text(rec.status.value),
                rec.agent_id,
                cost_str,
                latency,
            )

        panel = make_panel(
            RichGroup(header, Text(), status_line, Text(), table),
            title="Dashboard",
            subtitle=f"run: {run_id}",
        )
        get_console().print(panel)
    else:
        # Plain text fallback
        click.echo(f"  === Dashboard: {_short_id(run_id)} ===")
        click.echo(f"  Workflow: {run.workflow_name}")
        cost_str = f"Cost: ${run.total_cost:.4f}  " if run.total_cost else ""
        click.echo(
            f"  Status: {run.status}  "
            f"Nodes: {run.completed_nodes}/{run.total_nodes}  "
            f"{cost_str}"
            f"{_time_ago(run.started_at)}"
        )
        click.echo()
        if records:
            click.echo("  Nodes:")
            for rec in records:
                latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
                nc = node_costs.get(rec.task_id)
                nc_str = f"${nc:.4f}" if nc else ""
                click.echo(
                    f"    {rec.task_id:<20} {rec.status.value:<12} "
                    f"{rec.agent_id:<20} {nc_str:<10} {latency}"
                )
        else:
            click.echo("  (no execution records)")
        click.echo()


def _print_dashboard_menu() -> None:
    """Print action key hints."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        hint = Text()
        for key, label in [
            ("t", "trace"), ("g", "graph"), ("d", "debug"),
            ("c", "cost"), ("a", "artifacts"), ("n", "node"),
            ("r", "replay"), ("q", "quit"),
        ]:
            hint.append("  [", style="dim")
            hint.append(key, style="cyan bold")
            hint.append(f"] {label}", style="dim")
        get_console().print(hint)
    else:
        click.echo(
            "  [t]race [g]raph [d]ebug [c]ost [a]rtifacts [n]ode [r]eplay [q]uit"
        )


def _wait_for_enter() -> bool:
    """Prompt user to press Enter or q. Returns True if user wants to quit."""
    choice = click.prompt(
        "  [Enter] back to dashboard · [q] quit", default="",
    )
    return choice.strip().lower() == "q"


def _wait_for_enter_or_preview(node_arts: list) -> bool:
    """Prompt with preview option for node detail. Returns True if quit."""
    while True:
        choice = click.prompt(
            "  [Enter] back · [p] full preview · [q] quit", default="",
        )
        key = choice.strip().lower()
        if key == "q":
            return True
        if key == "p":
            _show_full_preview(node_arts)
            continue
        return False


def _show_full_preview(node_arts: list) -> None:
    """Render full artifact content as Rich Markdown panels."""
    if not node_arts:
        click.echo("  No artifacts to preview.")
        return

    for art in node_arts:
        content = art.content if art.content is not None else ""
        if not isinstance(content, str):
            content = json.dumps(content, default=str, indent=2)
        node = art.lineage.produced_by if art.lineage else "?"

        click.echo()
        if has_rich():
            from rich.markdown import Markdown

            from binex.cli.ui import get_console, make_panel

            console = get_console()
            console.print(make_panel(
                Markdown(content),
                title=f"[bold]{node}[/bold] / {art.type}",
                subtitle=f"id: {art.id}",
            ))
        else:
            click.echo(f"  ── {node} / {art.type} ──")
            click.echo(f"  {content}")
            click.echo(f"  id: {art.id}")


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def _action_trace(exec_store, run_id: str) -> None:
    """Show execution timeline."""
    if has_rich():
        try:
            from binex.trace.trace_rich import format_trace_rich
            await format_trace_rich(exec_store, run_id)
            return
        except ImportError:
            pass
    from binex.trace.tracer import generate_timeline
    output = await generate_timeline(exec_store, run_id)
    click.echo(output)


async def _action_graph(exec_store, run_id: str) -> None:
    """Show DAG visualization."""
    from binex.cli.trace import _build_graph_from_records, _render_dag

    records = await exec_store.list_records(run_id)
    if not records:
        click.echo("  No records found.")
        return

    nodes, edges = _build_graph_from_records(records)

    if has_rich():
        try:
            from binex.trace.trace_rich import format_trace_graph_rich
            await format_trace_graph_rich(records, nodes, edges)
            return
        except ImportError:
            pass

    click.echo("DAG:")
    _render_dag(nodes, edges, set(), click.echo)


async def _action_debug(exec_store, art_store, run_id: str) -> None:
    """Show debug report."""
    from binex.trace.debug_report import build_debug_report, format_debug_report

    report = await build_debug_report(exec_store, art_store, run_id)
    if report is None:
        click.echo("  No debug data available.")
        return

    if has_rich():
        try:
            from binex.trace.debug_rich import format_debug_report_rich
            format_debug_report_rich(report)
            return
        except ImportError:
            pass

    click.echo(format_debug_report(report))


async def _action_cost(exec_store, run_id: str) -> None:
    """Show cost breakdown."""
    from binex.cli.cost import print_cost_text

    cost_summary = await exec_store.get_run_cost_summary(run_id)
    cost_records = await exec_store.list_costs(run_id)
    print_cost_text(run_id, cost_summary, cost_records)


async def _action_artifacts(exec_store, art_store, run_id: str) -> None:
    """Artifact sub-browser: list → select → detail + lineage."""
    artifacts = await art_store.list_by_run(run_id)
    if not artifacts:
        click.echo(f"  No artifacts for run '{_short_id(run_id)}'.")
        return

    while True:
        click.echo()
        _print_artifacts_table(artifacts, run_id)
        click.echo()

        choice = click.prompt(
            "  Select artifact (or b=back)", default="b",
        )
        if choice.lower() == "b":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(artifacts):
                _show_artifact_detail(artifacts[idx])
                # Offer lineage
                lc = click.prompt(
                    "  [l] lineage  [b] back", default="b",
                )
                if lc.lower() == "l":
                    await _show_lineage(art_store, artifacts[idx].id)
                continue
        except ValueError:
            pass
        click.echo(f"  Invalid choice. Enter 1-{len(artifacts)} or b.")


def _print_artifacts_table(artifacts, run_id: str) -> None:
    """Display artifacts as a table (rich or plain)."""
    if has_rich():
        from binex.cli.ui import get_console, make_table

        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Node", {"style": "magenta", "min_width": 16}),
            ("Type", {"style": "yellow", "min_width": 10}),
            ("Preview", {"min_width": 30}),
            title=f"Artifacts — {_short_id(run_id)}",
        )

        for i, art in enumerate(artifacts, 1):
            node = art.lineage.produced_by if art.lineage else "?"
            table.add_row(str(i), node, art.type, _preview(art.content, max_len=60))
        get_console().print(table)
    else:
        click.echo(f"  Artifacts for {_short_id(run_id)}:")
        click.echo()
        for i, art in enumerate(artifacts, 1):
            node = art.lineage.produced_by if art.lineage else "?"
            click.echo(
                f"  {i:>3})  {node:<20} {art.type:<12} {_preview(art.content)}"
            )


def _show_artifact_detail(artifact) -> None:
    """Render artifact detail."""
    content_str = artifact.content if artifact.content is not None else ""
    if not isinstance(content_str, str):
        content_str = json.dumps(content_str, default=str, indent=2)

    node = artifact.lineage.produced_by if artifact.lineage else "?"

    if has_rich():
        from rich.markdown import Markdown
        from rich.text import Text

        from binex.cli.ui import STATUS_CONFIG, get_console, make_panel

        console = get_console()
        meta = Text()
        meta.append("Node: ", style="dim")
        meta.append(node, style="magenta bold")
        meta.append("  Type: ", style="dim")
        meta.append(artifact.type, style="yellow")
        meta.append("  Status: ", style="dim")
        _, style = STATUS_CONFIG.get(artifact.status, (artifact.status, "dim"))
        meta.append(artifact.status, style=style)
        console.print(meta)
        console.print()
        console.print(make_panel(
            Markdown(content_str),
            title=f"{node} / {artifact.type}",
            subtitle=f"id: {artifact.id}",
        ))
    else:
        click.echo(f"  -- {node} / {artifact.type} --")
        click.echo(f"  {content_str}")
        click.echo(f"  id: {artifact.id}")
        click.echo()


async def _show_lineage(art_store, artifact_id: str) -> None:
    """Display artifact lineage tree."""
    tree = await build_lineage_tree(art_store, artifact_id)
    if not tree:
        click.echo("  No lineage data available.")
        return

    click.echo()
    if has_rich():
        from rich.tree import Tree as RichTree

        from binex.cli.ui import get_console, make_panel

        def _build_rich_tree(node, parent=None):
            label = (
                f"[magenta bold]{node['produced_by']}[/] "
                f"[dim]({node['artifact_id']})[/] "
                f"[yellow]{node['type']}[/]"
            )
            if parent is None:
                branch = RichTree(label, guide_style="cyan")
            else:
                branch = parent.add(label)
            for p in node["parents"]:
                _build_rich_tree(p, branch)
            return branch

        rich_tree = _build_rich_tree(tree)
        get_console().print(make_panel(rich_tree, title="Artifact Lineage"))
    else:
        click.echo(format_lineage_tree(tree))


async def _action_node(exec_store, art_store, run_id: str, records) -> list:
    """Show numbered list of nodes, select one for detail. Returns node artifacts."""
    if not records:
        click.echo("  No execution records.")
        return []

    click.echo()
    if has_rich():
        from binex.cli.ui import get_console, make_table, status_text

        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Node", {"style": "bold", "min_width": 14}),
            ("Status", {"min_width": 10}),
            ("Agent", {"style": "dim"}),
            ("Latency", {"justify": "right"}),
            title="Select Node",
        )
        for i, rec in enumerate(records, 1):
            table.add_row(
                str(i),
                rec.task_id,
                status_text(rec.status.value),
                rec.agent_id,
                f"{rec.latency_ms}ms" if rec.latency_ms else "-",
            )
        get_console().print(table)
    else:
        for i, rec in enumerate(records, 1):
            latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
            click.echo(
                f"  {i:>3})  {rec.task_id:<20} {rec.status.value:<12} {latency}"
            )
    click.echo()

    choice = click.prompt("  Select node (or b=back)", default="b")
    if choice.lower() == "b":
        return []

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(records):
            rec = records[idx]

            # Gather node data
            artifacts = await art_store.list_by_run(run_id)
            node_arts = [
                a for a in artifacts
                if a.lineage and a.lineage.produced_by == rec.task_id
            ]
            costs = await exec_store.list_costs(run_id)
            node_costs = [c for c in costs if c.task_id == rec.task_id]
            node_total_cost = sum(c.cost for c in node_costs)

            click.echo()
            if has_rich():
                _render_node_rich(rec, node_arts, node_total_cost)
            else:
                _render_node_plain(rec, node_arts, node_total_cost)
            return node_arts
        else:
            click.echo(f"  Invalid choice. Enter 1-{len(records)} or b.")
    except ValueError:
        click.echo(f"  Invalid choice. Enter 1-{len(records)} or b.")
    return []


def _render_node_rich(rec, node_arts, node_total_cost: float) -> None:
    """Render node detail as a Rich panel."""
    from rich.console import Group
    from rich.text import Text

    from binex.cli.ui import STATUS_CONFIG, get_console, make_panel, make_table

    console = get_console()

    _, style = STATUS_CONFIG.get(rec.status.value, (rec.status.value, "dim"))

    # Info lines
    info = Text()
    info.append("Agent: ", style="dim")
    info.append(rec.agent_id, style="bold")
    info.append("  ·  Status: ", style="dim")
    info.append(rec.status.value, style=style)
    latency = f"{rec.latency_ms}ms" if rec.latency_ms else "-"
    info.append(f"  ·  Latency: {latency}", style="dim")
    if node_total_cost > 0:
        info.append(f"  ·  Cost: ${node_total_cost:.4f}", style="cyan")

    parts = [info]

    if rec.model:
        model_line = Text()
        model_line.append("Model: ", style="dim")
        model_line.append(rec.model)
        parts.append(model_line)

    if rec.error:
        err_line = Text()
        err_line.append("Error: ", style="red bold")
        err_line.append(rec.error, style="red")
        parts.append(err_line)

    # Artifacts table
    if node_arts:
        parts.append(Text())
        art_table = make_table(
            ("ID", {"style": "dim", "min_width": 16}),
            ("Type", {"style": "yellow", "min_width": 10}),
            ("Preview", {"min_width": 30}),
            title=f"Artifacts ({len(node_arts)})",
        )
        for art in node_arts:
            art_table.add_row(
                art.id[:16], art.type, _preview(art.content, max_len=60),
            )
        parts.append(art_table)

    panel = make_panel(
        Group(*parts),
        title=f"[bold]{rec.task_id}[/bold]",
        subtitle=f"run: {rec.run_id}" if hasattr(rec, "run_id") else None,
    )
    console.print(panel)


def _render_node_plain(rec, node_arts, node_total_cost: float) -> None:
    """Render node detail in plain text."""
    click.echo(f"  Node: {rec.task_id}")
    click.echo(f"  Agent: {rec.agent_id}")
    click.echo(f"  Status: {rec.status.value}")
    click.echo(f"  Latency: {rec.latency_ms}ms" if rec.latency_ms else "  Latency: -")
    if rec.model:
        click.echo(f"  Model: {rec.model}")
    if rec.error:
        click.echo(f"  Error: {rec.error}")
    if node_arts:
        click.echo(f"  Artifacts: {len(node_arts)}")
        for art in node_arts:
            click.echo(f"    - {art.id} ({art.type}): {_preview(art.content)}")
    if node_total_cost > 0:
        click.echo(f"  Cost: ${node_total_cost:.4f}")


async def _action_replay(exec_store, art_store, run_id: str, run, records) -> str | None:
    """Replay wizard: select start node, agent swaps, workflow path, confirm."""
    if run.status == "running":
        if has_rich():
            from binex.cli.ui import get_console as rc
            rc().print("  [yellow]⚠[/yellow] Cannot replay a running workflow.")
        else:
            click.echo("  Cannot replay a running workflow.")
        return

    if not records:
        click.echo("  No execution records to replay from.")
        return

    # Step 1: select start node
    click.echo()
    if has_rich():
        from binex.cli.ui import get_console, make_table, status_text

        console = get_console()
        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Node", {"style": "bold", "min_width": 14}),
            ("Status", {"min_width": 10}),
            ("Agent", {"style": "dim"}),
            title="Replay — select start node",
        )
        for i, rec in enumerate(records, 1):
            table.add_row(
                str(i), rec.task_id,
                status_text(rec.status.value), rec.agent_id,
            )
        console.print(table)
    else:
        click.echo("  Replay wizard — select start node:")
        for i, rec in enumerate(records, 1):
            click.echo(f"  {i:>3})  {rec.task_id}")
    click.echo()

    choice = click.prompt("  Start from node (or c=cancel)", default="c")
    if choice.lower() == "c":
        click.echo("  Replay cancelled.")
        return

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(records)):
            click.echo("  Invalid node selection. Replay cancelled.")
            return
    except ValueError:
        click.echo("  Invalid node selection. Replay cancelled.")
        return

    from_step = records[idx].task_id

    # Step 2: agent swaps
    agent_swaps: dict[str, str] = {}
    rec_map = {rec.task_id: rec for rec in records}
    while True:
        if has_rich():
            from rich.text import Text as SwapText

            from binex.cli.ui import get_console as swap_console
            from binex.cli.ui import make_table as swap_table

            if agent_swaps:
                t = swap_table(
                    ("Node", {"style": "bold", "min_width": 14}),
                    ("Original Agent", {"style": "dim"}),
                    ("New Agent", {"style": "cyan bold"}),
                    title="Agent Swaps",
                )
                for node, new_agent in agent_swaps.items():
                    orig = rec_map[node].agent_id if node in rec_map else "?"
                    t.add_row(node, orig, new_agent)
                swap_console().print(t)

            hint = SwapText()
            hint.append("  Format: ", style="dim")
            hint.append("node=agent", style="cyan")
            hint.append("  (e.g. ", style="dim")
            hint.append("draft=llm://gpt-4o", style="cyan")
            hint.append(")", style="dim")
            swap_console().print(hint)

        swap = click.prompt("  Agent swap (or done)", default="done")
        if swap.lower() == "done":
            break
        if "=" in swap:
            parts = swap.split("=", 1)
            node_name = parts[0].strip()
            agent_uri = parts[1].strip()
            if node_name not in rec_map:
                click.echo(f"  Node '{node_name}' not found. Available: {', '.join(rec_map)}")
            else:
                agent_swaps[node_name] = agent_uri
                if has_rich():
                    from binex.cli.ui import get_console as sc2
                    sc2().print(f"  [green]✓[/green] {node_name} → [cyan]{agent_uri}[/cyan]")
                else:
                    click.echo(f"  ✓ {node_name} → {agent_uri}")
        else:
            click.echo("  Format: node=agent (e.g. step2=llm://gpt-4o)")

    # Step 3: workflow path — use stored workflow_path from run, or prompt
    default_path = run.workflow_path
    if default_path:
        if has_rich():
            from binex.cli.ui import get_console as wf_console
            wf_console().print(
                f"  [dim]Workflow path from original run:[/dim] [cyan]{default_path}[/cyan]"
            )
        change = click.prompt("  Change workflow path? (y/n)", default="n")
        if change.strip().lower() == "y":
            workflow = click.prompt(
                "  Workflow file path", default=default_path,
            ).strip().strip("'\"")
        else:
            workflow = default_path
    else:
        if has_rich():
            from binex.cli.ui import get_console as wf_console
            wf_console().print("  [dim]Enter path to workflow YAML file[/dim]")
        workflow = click.prompt("  Workflow file path").strip().strip("'\"")

    # Step 4: confirm
    click.echo()
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        summary_lines = Text()
        summary_lines.append("From node: ", style="dim")
        summary_lines.append(from_step, style="bold")
        summary_lines.append("\nWorkflow: ", style="dim")
        summary_lines.append(workflow)
        if agent_swaps:
            summary_lines.append("\nAgent swaps:", style="dim")
            for node, agent in agent_swaps.items():
                summary_lines.append(f"\n  {node}", style="magenta")
                summary_lines.append(" → ", style="dim")
                summary_lines.append(agent, style="cyan")
        get_console().print(make_panel(summary_lines, title="Replay Summary"))
    else:
        click.echo(f"  Replay from: {from_step}")
        if agent_swaps:
            click.echo(f"  Agent swaps: {agent_swaps}")
        click.echo(f"  Workflow: {workflow}")
    confirm = click.prompt("  Confirm? (y/n)", default="n")
    if confirm.lower() != "y":
        click.echo("  Replay cancelled.")
        return

    # Step 5: execute replay
    try:
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.runtime.replay import ReplayEngine
        from binex.workflow_spec.loader import load_workflow

        spec = load_workflow(workflow)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
        )
        register_workflow_adapters(
            engine.dispatcher, spec, agent_swaps=agent_swaps,
        )
        summary = await engine.replay(
            original_run_id=run_id,
            workflow=spec,
            from_step=from_step,
            agent_swaps=agent_swaps,
        )
        if has_rich():
            from rich.text import Text as RText

            from binex.cli.ui import STATUS_CONFIG, make_panel
            from binex.cli.ui import get_console as gc

            result_text = RText()
            result_text.append("New Run: ", style="dim")
            result_text.append(summary.run_id, style="cyan")
            result_text.append("\nStatus: ", style="dim")
            _, st = STATUS_CONFIG.get(summary.status, (summary.status, "dim"))
            result_text.append(summary.status, style=st)
            result_text.append(
                f"\nNodes: {summary.completed_nodes}/{summary.total_nodes}",
                style="dim",
            )
            gc().print(make_panel(result_text, title="Replay Complete"))
        else:
            click.echo(f"  Replay complete. New run: {summary.run_id}")
            click.echo(f"  Status: {summary.status}")
        return summary.run_id
    except Exception as exc:
        if has_rich():
            from binex.cli.ui import get_console as fc
            fc().print(f"  [red bold]✗ Replay failed:[/red bold] {exc}")
        else:
            click.echo(f"  Replay failed: {exc}")
        return None
