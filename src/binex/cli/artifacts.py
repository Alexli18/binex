"""CLI `binex artifacts` command — manage and inspect artifacts."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores
from binex.trace.lineage import build_lineage_tree, format_lineage_tree


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.group("artifacts")
def artifacts_cmd() -> None:
    """Manage and inspect artifacts."""


@artifacts_cmd.command("list")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def artifacts_list_cmd(run_id: str, json_out: bool) -> None:
    """List all artifacts for a run."""
    asyncio.run(_list(run_id, json_out))


async def _list(run_id: str, json_out: bool) -> None:
    exec_store, art_store = _get_stores()
    try:
        artifacts = await art_store.list_by_run(run_id)
        if json_out:
            data = [a.model_dump() for a in artifacts]
            click.echo(json.dumps(data, default=str, indent=2))
        else:
            if not artifacts:
                click.echo(f"No artifacts found for run '{run_id}'.")
                return
            for art in artifacts:
                click.echo(f"  {art.id:<25} type={art.type:<20} status={art.status}")
    finally:
        await exec_store.close()


@artifacts_cmd.command("show")
@click.argument("artifact_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def artifacts_show_cmd(artifact_id: str, json_out: bool) -> None:
    """Display artifact content."""
    asyncio.run(_show(artifact_id, json_out))


async def _show(artifact_id: str, json_out: bool) -> None:
    exec_store, art_store = _get_stores()
    try:
        artifact = await art_store.get(artifact_id)
        if artifact is None:
            click.echo(f"Error: Artifact '{artifact_id}' not found.", err=True)
            sys.exit(1)

        if json_out:
            click.echo(json.dumps(artifact.model_dump(), default=str, indent=2))
        else:
            click.echo(f"ID: {artifact.id}")
            click.echo(f"Type: {artifact.type}")
            click.echo(f"Run: {artifact.run_id}")
            click.echo(f"Status: {artifact.status}")
            click.echo(f"Produced by: {artifact.lineage.produced_by}")
            if artifact.lineage.derived_from:
                click.echo(f"Derived from: {', '.join(artifact.lineage.derived_from)}")
            click.echo(f"Content: {json.dumps(artifact.content, default=str)}")
    finally:
        await exec_store.close()


@artifacts_cmd.command("lineage")
@click.argument("artifact_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def artifacts_lineage_cmd(artifact_id: str, json_out: bool) -> None:
    """Show full provenance chain (tree view)."""
    asyncio.run(_lineage(artifact_id, json_out))


async def _lineage(artifact_id: str, json_out: bool) -> None:
    exec_store, art_store = _get_stores()
    try:
        tree = await build_lineage_tree(art_store, artifact_id)
        if tree is None:
            click.echo(f"Error: Artifact '{artifact_id}' not found.", err=True)
            sys.exit(1)

        if json_out:
            click.echo(json.dumps(tree, default=str, indent=2))
        else:
            click.echo(format_lineage_tree(tree))
    finally:
        await exec_store.close()
