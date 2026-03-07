"""CLI `binex diff` command — compare two runs."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from binex.cli import get_stores


@click.command("diff")
@click.argument("run_a")
@click.argument("run_b")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def diff_cmd(run_a: str, run_b: str, json_out: bool) -> None:
    """Compare two runs side-by-side."""
    try:
        result = asyncio.run(_run_diff(run_a, run_b))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_out:
        click.echo(json.dumps(result, default=str, indent=2))
    else:
        from binex.trace.diff import format_diff
        click.echo(format_diff(result))


async def _run_diff(run_a: str, run_b: str) -> dict[str, Any]:
    from binex.trace.diff import diff_runs

    exec_store, art_store = get_stores()
    try:
        return await diff_runs(exec_store, art_store, run_a, run_b)
    finally:
        await exec_store.close()
