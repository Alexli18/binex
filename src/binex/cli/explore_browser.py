"""Explore run browser — list and select runs."""

from __future__ import annotations

import click

from binex.cli import has_rich
from binex.cli.explore_utils import _short_id, _time_ago


async def _browse_runs(exec_store, art_store, dashboard_fn) -> None:
    """List recent runs and let user pick one for the dashboard."""
    while True:
        runs = await exec_store.list_runs()
        if not runs:
            click.echo("No runs found. Run a workflow first:")
            click.echo("  binex run examples/simple.yaml --var input=\"hello\"")
            return

        runs.sort(key=lambda r: r.started_at, reverse=True)
        runs = runs[:20]

        click.echo()
        if has_rich():
            _render_runs_rich(runs)
        else:
            _render_runs_plain(runs)
        click.echo()

        selected = await _select_run(exec_store, art_store, runs, dashboard_fn)
        if selected == "quit":
            return
        # selected == "refresh" → back to outer loop


def _render_runs_rich(runs) -> None:
    """Render runs table with Rich formatting."""
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
            str(i), _short_id(run.run_id), run.workflow_name,
            status_text(run.status), nodes, cost_str, _time_ago(run.started_at),
        )
    get_console().print(table)


def _render_runs_plain(runs) -> None:
    """Render runs list in plain text."""
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


async def _select_run(exec_store, art_store, runs, dashboard_fn) -> str:
    """Prompt user to select a run. Returns 'quit' or 'refresh'."""
    while True:
        choice = click.prompt("  Select run (or q to quit)", default="1")
        if choice.lower() == "q":
            return "quit"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(runs):
                quit_all = await dashboard_fn(exec_store, art_store, runs[idx].run_id)
                if quit_all:
                    return "quit"
                return "refresh"
        except ValueError:
            pass
        click.echo(f"  Invalid choice. Enter 1-{len(runs)} or q.")
