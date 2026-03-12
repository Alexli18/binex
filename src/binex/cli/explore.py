"""CLI `binex explore` command — interactive dashboard for runs."""

from __future__ import annotations

import asyncio

import click

from binex.cli import get_stores
from binex.cli.explore_actions import (
    _action_artifacts,
    _action_bisect,
    _action_cost,
    _action_debug,
    _action_diagnose,
    _action_diff,
    _action_graph,
    _action_node,
    _action_trace,
)
from binex.cli.explore_browser import _browse_runs
from binex.cli.explore_replay import _action_replay
from binex.cli.explore_ui import (
    _print_dashboard_menu,
    _render_dashboard,
    _wait_for_enter,
    _wait_for_enter_or_preview,
)

# Re-export utilities so existing imports from binex.cli.explore still work
from binex.cli.explore_utils import _preview, _short_id, _time_ago  # noqa: F401


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


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
            await _browse_runs(exec_store, art_store, _dashboard)
    finally:
        await exec_store.close()


async def _dashboard(exec_store, art_store, run_id: str) -> bool:
    """Core dashboard: render summary + node table, then action menu loop.

    Returns True to quit explore entirely, False to go back to run list.
    """
    while True:
        run = await exec_store.get_run(run_id)
        if run is None:
            click.echo(f"Run '{run_id}' not found.")
            return True
        records = await exec_store.list_records(run_id)
        cost_records = await exec_store.list_costs(run_id)

        click.echo()
        _render_dashboard(run, records, run_id, cost_records)
        _print_dashboard_menu()

        choice = click.prompt("  Action", default="q")
        key = choice.strip()

        if key in ("q", "Q"):
            return key == "Q"

        result = await _dispatch_action(
            key.lower(), exec_store, art_store, run_id, run, records,
        )
        if result == "continue":
            continue
        if result == "back":
            return False
        if isinstance(result, str) and result.startswith("switch:"):
            run_id = result[len("switch:"):]
            continue

        if _wait_for_enter():
            return False


async def _dispatch_action(
    key: str, exec_store, art_store, run_id: str, run, records,
) -> str | None:
    """Dispatch a single dashboard action. Returns control signal or None."""
    # Actions that need only exec_store
    _exec_actions: dict[str, str] = {"t": "trace", "g": "graph", "c": "cost"}
    # Actions that need exec_store + art_store
    _both_actions: dict[str, str] = {"d": "debug", "a": "artifacts", "i": "diagnose"}
    # Actions that also need run
    _run_actions: dict[str, str] = {"f": "diff", "b": "bisect"}

    if key == "n":
        return await _dispatch_node(exec_store, art_store, run_id, records)
    if key == "r":
        return await _dispatch_replay(exec_store, art_store, run_id, run, records)

    if key in _exec_actions:
        handler = {
            "t": lambda: _action_trace(exec_store, run_id),
            "g": lambda: _action_graph(exec_store, run_id),
            "c": lambda: _action_cost(exec_store, run_id),
        }
        await handler[key]()
    elif key in _both_actions:
        handler = {
            "d": lambda: _action_debug(exec_store, art_store, run_id),
            "a": lambda: _action_artifacts(exec_store, art_store, run_id),
            "i": lambda: _action_diagnose(exec_store, art_store, run_id),
        }
        await handler[key]()
    elif key in _run_actions:
        handler = {
            "f": lambda: _action_diff(exec_store, art_store, run_id, run),
            "b": lambda: _action_bisect(exec_store, art_store, run_id, run),
        }
        await handler[key]()
    else:
        click.echo("  Unknown action. Use t/g/d/c/a/n/r/i/f/b/q/Q.")
        return "continue"
    return None


async def _dispatch_node(exec_store, art_store, run_id: str, records) -> str | None:
    """Handle node inspection action."""
    node_arts = await _action_node(exec_store, art_store, run_id, records)
    if node_arts:
        if _wait_for_enter_or_preview(node_arts):
            return "back"
        return "continue"
    return None


async def _dispatch_replay(exec_store, art_store, run_id: str, run, records) -> str:
    """Handle replay action with post-replay navigation."""
    new_run_id = await _action_replay(exec_store, art_store, run_id, run, records)
    if new_run_id:
        choice = click.prompt(
            "  [Enter] back · [e] explore new run · [q] back to runs",
            default="",
        )
        k = choice.strip().lower()
        if k == "q":
            return "back"
        if k == "e":
            return f"switch:{new_run_id}"
    return "continue"
