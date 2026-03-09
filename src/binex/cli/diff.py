"""CLI `binex diff` command — compare two runs."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from binex.cli import get_stores


def _has_rich() -> bool:
    try:
        import rich  # noqa: F401
        return True
    except ImportError:
        return False


@click.command("diff")
@click.argument("run_a")
@click.argument("run_b")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
def diff_cmd(run_a: str, run_b: str, json_out: bool, rich_out: bool | None) -> None:
    """Compare two runs side-by-side."""
    if rich_out is None:
        rich_out = _has_rich()
    try:
        result = asyncio.run(_run_diff(run_a, run_b))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_out:
        click.echo(json.dumps(result, default=str, indent=2))
    elif rich_out:
        from binex.trace.diff_rich import format_diff_rich
        click.echo(format_diff_rich(result))
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
