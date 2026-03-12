"""Explore replay sub-flow — wizard for replaying workflow runs."""

from __future__ import annotations

import click

from binex.cli import has_rich


async def _action_replay(exec_store, art_store, run_id: str, run, records) -> str | None:
    """Replay wizard: select start node, agent swaps, workflow path, confirm."""
    if run.status == "running":
        if has_rich():
            from binex.cli.ui import get_console as rc
            rc().print("  [yellow]\u26a0[/yellow] Cannot replay a running workflow.")
        else:
            click.echo("  Cannot replay a running workflow.")
        return None

    if not records:
        click.echo("  No execution records to replay from.")
        return None

    from_step = _replay_select_start_node(records)
    if from_step is None:
        return None

    rec_map = {rec.task_id: rec for rec in records}
    agent_swaps = _replay_collect_agent_swaps(rec_map)

    workflow = _replay_select_workflow(run.workflow_path)

    if not _replay_confirm(from_step, workflow, agent_swaps):
        return None

    return await _replay_execute(
        exec_store, art_store, run_id, workflow, from_step, agent_swaps,
    )


def _replay_select_start_node(records) -> str | None:
    """Step 1: let user pick start node for replay."""
    click.echo()
    if has_rich():
        from binex.cli.ui import get_console, make_table, status_text
        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Node", {"style": "bold", "min_width": 14}),
            ("Status", {"min_width": 10}),
            ("Agent", {"style": "dim"}),
            title="Replay \u2014 select start node",
        )
        for i, rec in enumerate(records, 1):
            table.add_row(str(i), rec.task_id, status_text(rec.status.value), rec.agent_id)
        get_console().print(table)
    else:
        click.echo("  Replay wizard \u2014 select start node:")
        for i, rec in enumerate(records, 1):
            click.echo(f"  {i:>3})  {rec.task_id}")
    click.echo()

    choice = click.prompt("  Start from node (or c=cancel)", default="c")
    if choice.lower() == "c":
        click.echo("  Replay cancelled.")
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(records):
            return records[idx].task_id
    except ValueError:
        pass
    click.echo("  Invalid node selection. Replay cancelled.")
    return None


def _replay_collect_agent_swaps(rec_map: dict) -> dict[str, str]:
    """Step 2: collect agent swaps interactively."""
    agent_swaps: dict[str, str] = {}
    while True:
        _render_swap_hint(agent_swaps, rec_map)

        swap = click.prompt("  Agent swap (or done)", default="done")
        if swap.lower() == "done":
            break
        if "=" not in swap:
            click.echo("  Format: node=agent (e.g. step2=llm://gpt-4o)")
            continue
        node_name, agent_uri = swap.split("=", 1)
        node_name, agent_uri = node_name.strip(), agent_uri.strip()
        if node_name not in rec_map:
            click.echo(f"  Node '{node_name}' not found. Available: {', '.join(rec_map)}")
            continue
        agent_swaps[node_name] = agent_uri
        if has_rich():
            from binex.cli.ui import get_console
            msg = f"  [green]\u2713[/green] {node_name} \u2192 [cyan]{agent_uri}[/cyan]"
            get_console().print(msg)
        else:
            click.echo(f"  \u2713 {node_name} \u2192 {agent_uri}")
    return agent_swaps


def _render_swap_hint(agent_swaps: dict, rec_map: dict) -> None:
    """Render current swaps table and format hint."""
    if not has_rich():
        return
    from rich.text import Text

    from binex.cli.ui import get_console, make_table

    if agent_swaps:
        t = make_table(
            ("Node", {"style": "bold", "min_width": 14}),
            ("Original Agent", {"style": "dim"}),
            ("New Agent", {"style": "cyan bold"}),
            title="Agent Swaps",
        )
        for node, new_agent in agent_swaps.items():
            orig = rec_map[node].agent_id if node in rec_map else "?"
            t.add_row(node, orig, new_agent)
        get_console().print(t)
    hint = Text()
    hint.append("  Format: ", style="dim")
    hint.append("node=agent", style="cyan")
    hint.append("  (e.g. ", style="dim")
    hint.append("draft=llm://gpt-4o", style="cyan")
    hint.append(")", style="dim")
    get_console().print(hint)


def _replay_select_workflow(default_path: str | None) -> str:
    """Step 3: select workflow path."""
    if default_path:
        if has_rich():
            from binex.cli.ui import get_console as wf_console
            wf_console().print(
                f"  [dim]Workflow path from original run:[/dim] [cyan]{default_path}[/cyan]"
            )
        change = click.prompt("  Change workflow path? (y/n)", default="n")
        if change.strip().lower() == "y":
            return click.prompt("  Workflow file path", default=default_path).strip().strip("'\"")
        return default_path
    if has_rich():
        from binex.cli.ui import get_console as wf_console
        wf_console().print("  [dim]Enter path to workflow YAML file[/dim]")
    return click.prompt("  Workflow file path").strip().strip("'\"")


def _replay_confirm(from_step: str, workflow: str, agent_swaps: dict) -> bool:
    """Step 4: show summary and ask for confirmation."""
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
                summary_lines.append(" \u2192 ", style="dim")
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
        return False
    return True


async def _replay_execute(
    exec_store, art_store, run_id: str,
    workflow_path: str, from_step: str, agent_swaps: dict,
) -> str | None:
    """Step 5: execute the replay and display results."""
    try:
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.runtime.replay import ReplayEngine
        from binex.workflow_spec.loader import load_workflow

        spec = load_workflow(workflow_path)
        engine = ReplayEngine(execution_store=exec_store, artifact_store=art_store)
        register_workflow_adapters(engine.dispatcher, spec, agent_swaps=agent_swaps)
        summary = await engine.replay(
            original_run_id=run_id, workflow=spec,
            from_step=from_step, agent_swaps=agent_swaps,
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
                f"\nNodes: {summary.completed_nodes}/{summary.total_nodes}", style="dim",
            )
            gc().print(make_panel(result_text, title="Replay Complete"))
        else:
            click.echo(f"  Replay complete. New run: {summary.run_id}")
            click.echo(f"  Status: {summary.status}")
        return summary.run_id
    except Exception as exc:
        if has_rich():
            from binex.cli.ui import get_console as fc
            fc().print(f"  [red bold]\u2717 Replay failed:[/red bold] {exc}")
        else:
            click.echo(f"  Replay failed: {exc}")
        return None
