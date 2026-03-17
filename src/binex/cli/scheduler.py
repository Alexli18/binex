"""CLI `binex scheduler` command group — start, list, add, remove."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from binex.scheduler.engine import SchedulerEngine, scan_directory
from binex.scheduler.models import ScheduledWorkflow
from binex.scheduler.state import DEFAULT_STATE_PATH, load_state, save_state


def _collect_workflows(
    directory: Path | None,
    state_path: Path = DEFAULT_STATE_PATH,
) -> list[ScheduledWorkflow]:
    """Collect workflows from directory scan + registered paths."""
    workflows: list[ScheduledWorkflow] = []
    seen_paths: set[str] = set()

    if directory:
        for wf in scan_directory(directory):
            workflows.append(wf)
            seen_paths.add(wf.path)

    state = load_state(state_path)
    for path_str in state.registered:
        if path_str in seen_paths:
            continue
        p = Path(path_str)
        if not p.exists():
            click.echo(f"Warning: registered file not found: {path_str}", err=True)
            continue
        found = scan_directory(p.parent)
        for wf in found:
            if wf.path == path_str and wf.path not in seen_paths:
                workflows.append(wf)
                seen_paths.add(wf.path)

    return workflows


@click.group("scheduler", epilog="""\b
Examples:
  binex scheduler start .                 Start scheduler for current directory
  binex scheduler list .                  List discovered scheduled workflows
  binex scheduler add workflow.yaml       Register a workflow file
  binex scheduler remove workflow.yaml    Unregister a workflow file
""")
def scheduler_group() -> None:
    """Manage cron-based workflow scheduling."""


@scheduler_group.command("start")
@click.argument("directory", default=".", type=click.Path(exists=True, file_okay=False))
def scheduler_start_cmd(directory: str) -> None:
    """Start the scheduler for a directory (foreground)."""
    dir_path = Path(directory).resolve()
    state_path = dir_path / ".binex" / "scheduler.json"
    workflows = _collect_workflows(dir_path, state_path)

    if not workflows:
        click.echo("No workflows with schedule field found.")
        sys.exit(0)

    click.echo(f"Starting scheduler with {len(workflows)} workflow(s):")
    for wf in workflows:
        click.echo(f"  {wf.name}  [{wf.schedule}]  next: {wf.next_run:%Y-%m-%d %H:%M}")

    state = load_state(state_path)
    engine = SchedulerEngine(
        workflows=workflows,
        state=state,
        state_path=state_path,
        scan_dir=dir_path,
    )
    asyncio.run(engine.run_loop())


@scheduler_group.command("list")
@click.argument("directory", default=".", type=click.Path(exists=True, file_okay=False))
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def scheduler_list_cmd(directory: str, json_out: bool) -> None:
    """List all scheduled workflows in a directory."""
    dir_path = Path(directory).resolve()
    state_path = dir_path / ".binex" / "scheduler.json"
    workflows = _collect_workflows(dir_path, state_path)

    if json_out:
        data = [
            {
                "name": wf.name,
                "schedule": wf.schedule,
                "path": wf.path,
                "next_run": wf.next_run.isoformat(),
            }
            for wf in workflows
        ]
        click.echo(json.dumps(data, indent=2))
        return

    if not workflows:
        click.echo("No scheduled workflows found.")
        return

    click.echo(f"Scheduled workflows ({len(workflows)}):\n")
    for wf in workflows:
        click.echo(f"  {wf.name}")
        click.echo(f"    schedule: {wf.schedule}")
        click.echo(f"    path:     {wf.path}")
        click.echo(f"    next_run: {wf.next_run:%Y-%m-%d %H:%M UTC}")
        click.echo()


@scheduler_group.command("add")
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
def scheduler_add_cmd(file: str) -> None:
    """Register a workflow file for scheduling."""
    abs_path = str(Path(file).resolve())
    state = load_state(DEFAULT_STATE_PATH)

    if abs_path in state.registered:
        click.echo(f"Already registered: {abs_path}")
        return

    state.registered.append(abs_path)
    save_state(state, DEFAULT_STATE_PATH)
    click.echo(f"Registered: {abs_path}")


@scheduler_group.command("remove")
@click.argument("file", type=click.Path())
def scheduler_remove_cmd(file: str) -> None:
    """Unregister a workflow file from scheduling."""
    abs_path = str(Path(file).resolve())
    state = load_state(DEFAULT_STATE_PATH)

    if abs_path not in state.registered:
        click.echo(f"Not registered: {abs_path}")
        return

    state.registered.remove(abs_path)
    save_state(state, DEFAULT_STATE_PATH)
    click.echo(f"Removed: {abs_path}")
