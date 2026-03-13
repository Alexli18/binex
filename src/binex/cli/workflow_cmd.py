"""CLI `binex workflow` command group."""

from __future__ import annotations

import asyncio
import difflib

import click
import yaml

from binex.cli import get_stores


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.group("workflow")
def workflow_group() -> None:
    """Workflow versioning and inspection commands."""


@workflow_group.command("version")
@click.argument("workflow_file", type=click.Path(exists=True))
def version_cmd(workflow_file: str) -> None:
    """Display the schema version of a workflow file."""
    from pathlib import Path

    content = Path(workflow_file).read_text()
    data = yaml.safe_load(content)
    name = data.get("name", "unknown")
    version = data.get("version")
    if version is None:
        click.echo(f"Workflow: {name}")
        click.echo("Version: 1 (default — no version field found)")
    else:
        click.echo(f"Workflow: {name}")
        click.echo(f"Version: {version}")


@workflow_group.command("diff")
@click.argument("run_id_1")
@click.argument("run_id_2")
def diff_cmd(run_id_1: str, run_id_2: str) -> None:
    """Compare workflows used in two different runs."""
    asyncio.run(_diff(run_id_1, run_id_2))


async def _diff(run_id_1: str, run_id_2: str) -> None:
    store, _ = _get_stores()
    try:
        if not hasattr(store, "get_workflow_snapshot"):
            click.echo("Error: Store does not support workflow snapshots.", err=True)
            return

        run1 = await store.get_run(run_id_1)
        run2 = await store.get_run(run_id_2)

        if run1 is None:
            click.echo(f"Error: Run '{run_id_1}' not found.", err=True)
            return
        if run2 is None:
            click.echo(f"Error: Run '{run_id_2}' not found.", err=True)
            return

        hash1 = run1.workflow_hash
        hash2 = run2.workflow_hash

        if not hash1 or not hash2:
            click.echo("Error: One or both runs have no workflow snapshot.", err=True)
            return

        if hash1 == hash2:
            click.echo("Workflows are identical (no diff).")
            return

        snap1 = await store.get_workflow_snapshot(hash1)
        snap2 = await store.get_workflow_snapshot(hash2)

        if not snap1 or not snap2:
            click.echo("Error: Snapshot data missing.", err=True)
            return

        diff_output = difflib.unified_diff(
            snap1["content"].splitlines(keepends=True),
            snap2["content"].splitlines(keepends=True),
            fromfile=f"run:{run_id_1}",
            tofile=f"run:{run_id_2}",
        )
        output = "".join(diff_output)
        if output:
            click.echo(output)
        else:
            click.echo("Workflows are identical (no diff).")
    finally:
        await store.close()
