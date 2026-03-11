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
        for i, run in enumerate(runs, 1):
            from binex.cli.ui import STATUS_CONFIG
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

        click.echo()
        _render_dashboard(run, records, run_id)
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
            await _action_node(exec_store, art_store, run_id, records)
        elif key == "r":
            await _action_replay(exec_store, run_id, run, records)
        else:
            click.echo("  Unknown action. Use t/g/d/c/a/n/r/q.")
            continue

        if _wait_for_enter():
            return


def _render_dashboard(run, records, run_id: str) -> None:
    """Render dashboard panel with header, status, and node table."""
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
            ("Latency", {"justify": "right"}),
        )
        for rec in records:
            latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
            table.add_row(
                rec.task_id,
                status_text(rec.status.value),
                rec.agent_id,
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
        click.echo(
            f"  Status: {run.status}  "
            f"Nodes: {run.completed_nodes}/{run.total_nodes}  "
            f"Cost: ${run.total_cost:.4f}  "
            f"{_time_ago(run.started_at)}"
        )
        click.echo()
        if records:
            click.echo("  Nodes:")
            for rec in records:
                latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
                click.echo(
                    f"    {rec.task_id:<20} {rec.status.value:<12} "
                    f"{rec.agent_id:<20} {latency}"
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
    from binex.cli.cost import _print_cost_text

    cost_summary = await exec_store.get_run_cost_summary(run_id)
    cost_records = await exec_store.list_costs(run_id)
    _print_cost_text(run_id, cost_summary, cost_records)


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


async def _action_node(exec_store, art_store, run_id: str, records) -> None:
    """Show numbered list of nodes, select one for detail."""
    if not records:
        click.echo("  No execution records.")
        return

    click.echo()
    for i, rec in enumerate(records, 1):
        latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
        click.echo(
            f"  {i:>3})  {rec.task_id:<20} {rec.status.value:<12} {latency}"
        )
    click.echo()

    choice = click.prompt("  Select node (or b=back)", default="b")
    if choice.lower() == "b":
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(records):
            rec = records[idx]
            click.echo()
            click.echo(f"  Node: {rec.task_id}")
            click.echo(f"  Agent: {rec.agent_id}")
            click.echo(f"  Status: {rec.status.value}")
            click.echo(f"  Latency: {rec.latency_ms}ms")
            if rec.error:
                click.echo(f"  Error: {rec.error}")
            if rec.prompt:
                click.echo(f"  Prompt: {rec.prompt}")
            if rec.model:
                click.echo(f"  Model: {rec.model}")

            # Show artifacts for this node
            artifacts = await art_store.list_by_run(run_id)
            node_arts = [
                a for a in artifacts
                if a.lineage and a.lineage.produced_by == rec.task_id
            ]
            if node_arts:
                click.echo(f"  Artifacts: {len(node_arts)}")
                for art in node_arts:
                    click.echo(f"    - {art.id} ({art.type}): {_preview(art.content)}")

            # Show cost for this node
            costs = await exec_store.list_costs(run_id)
            node_costs = [c for c in costs if c.task_id == rec.task_id]
            if node_costs:
                total = sum(c.cost for c in node_costs)
                click.echo(f"  Cost: ${total:.4f}")
        else:
            click.echo(f"  Invalid choice. Enter 1-{len(records)} or b.")
    except ValueError:
        click.echo(f"  Invalid choice. Enter 1-{len(records)} or b.")


async def _action_replay(exec_store, run_id: str, run, records) -> None:
    """Replay wizard: select start node, agent swaps, workflow path, confirm."""
    if run.status == "running":
        click.echo("  Cannot replay a running workflow.")
        return

    if not records:
        click.echo("  No execution records to replay from.")
        return

    # Step 1: select start node
    click.echo()
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
    while True:
        swap = click.prompt(
            "  Agent swap (node=agent, or done)", default="done",
        )
        if swap.lower() == "done":
            break
        if "=" in swap:
            parts = swap.split("=", 1)
            agent_swaps[parts[0].strip()] = parts[1].strip()
        else:
            click.echo("  Format: node=agent (e.g. step2=llm://gpt-4o)")

    # Step 3: workflow path
    workflow = click.prompt("  Workflow file path")

    # Step 4: confirm
    click.echo()
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
        import subprocess
        result = subprocess.run(
            ["binex", "replay", run_id, "--from", from_step, "--workflow", workflow]
            + [
                arg
                for node, agent in agent_swaps.items()
                for arg in ["--agent", f"{node}={agent}"]
            ],
            capture_output=True,
            text=True,
        )
        click.echo(result.stdout)
        if result.stderr:
            click.echo(result.stderr)
    except Exception as exc:
        click.echo(f"  Replay failed: {exc}")
