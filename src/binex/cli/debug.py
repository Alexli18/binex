"""CLI command: binex debug <run_id> — post-mortem workflow inspection."""

from __future__ import annotations

import asyncio
import sys

import click

from binex.cli import get_stores
from binex.trace.debug_report import (
    build_debug_report,
    format_debug_report,
    format_debug_report_json,
)


def _has_rich() -> bool:
    """Check if rich is available."""
    try:
        import rich  # noqa: F401
        return True
    except ImportError:
        return False


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.command("debug")
@click.argument("run_id")
@click.option("--node", default=None, help="Show only the specified node")
@click.option("--errors", is_flag=True, help="Show only failed/timed_out nodes")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
def debug_cmd(
    run_id: str,
    node: str | None,
    errors: bool,
    json_out: bool,
    rich_out: bool | None,
) -> None:
    """Post-mortem inspection of a workflow run."""
    # Auto-detect rich if not explicitly set
    if rich_out is None:
        rich_out = _has_rich()

    result = asyncio.run(
        _debug_async(
            run_id,
            node_filter=node,
            errors_only=errors,
            json_out=json_out,
            rich_out=rich_out,
        )
    )
    if result is None:
        click.echo(f"Error: Run '{run_id}' not found.", err=True)
        sys.exit(1)
    click.echo(result)


async def _resolve_run_id(run_id: str, exec_store) -> str | None:
    """Resolve 'latest' to the most recent run ID."""
    if run_id != "latest":
        return run_id
    runs = await exec_store.list_runs()
    if not runs:
        return None
    runs.sort(key=lambda r: r.started_at, reverse=True)
    return runs[0].run_id


async def _debug_async(
    run_id: str,
    *,
    node_filter: str | None = None,
    errors_only: bool = False,
    json_out: bool = False,
    rich_out: bool = False,
) -> str | None:
    import json

    exec_store, art_store = _get_stores()
    try:
        run_id = await _resolve_run_id(run_id, exec_store)
        if run_id is None:
            return None
        report = await build_debug_report(exec_store, art_store, run_id)
        if report is None:
            return None
        if json_out:
            data = format_debug_report_json(report)
            return json.dumps(data, indent=2)
        if rich_out:
            try:
                from binex.trace.debug_rich import format_debug_report_rich
            except ImportError:
                pass
            else:
                return format_debug_report_rich(
                    report, node_filter=node_filter, errors_only=errors_only
                )
        return format_debug_report(
            report, node_filter=node_filter, errors_only=errors_only
        )
    finally:
        await exec_store.close()
