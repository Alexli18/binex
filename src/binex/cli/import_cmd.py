"""CLI group: ``binex import`` — import external trace data into Binex."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from binex.cli import get_stores


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.group("import")
def import_group() -> None:
    """Import external trace data (OTel, etc.) into Binex stores."""


@import_group.command("otel")
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--json", "as_json", is_flag=True,
    help="Output result as JSON.",
)
def import_otel(file: str, as_json: bool) -> None:
    """Import an OTLP/JSON trace file into the Binex store.

    FILE must be a valid OTLP JSON export (``ExportTraceServiceRequest``).

    \b
    Example:
      binex import otel trace.json
      binex import otel trace.json --json
    """
    try:
        summary = asyncio.run(_run_import(file))
    except Exception as exc:  # noqa: BLE001
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(summary, indent=2))
    else:
        click.echo(f"Run ID:       {summary['run_id']}")
        click.echo(f"Workflow:     {summary['workflow_name']}")
        click.echo(f"Nodes:        {summary['node_count']}")
        click.echo(f"Warnings:     {summary['warning_count']}")
        if summary["warnings"]:
            for w in summary["warnings"]:
                click.echo(f"  ! {w}", err=True)
    sys.exit(0)


async def _run_import(file: str) -> dict[str, Any]:
    from binex.importers.otel import import_from_file

    exec_store, art_store = _get_stores()
    try:
        result = await import_from_file(file, exec_store, art_store)
    finally:
        await exec_store.close()

    return {
        "run_id": result.run_summary.run_id,
        "workflow_name": result.run_summary.workflow_name,
        "node_count": len(result.records),
        "warning_count": len(result.warnings),
        "warnings": result.warnings,
        "artifact_count": len(result.artifacts),
        "cost_record_count": len(result.cost_records),
    }


__all__ = ["import_group"]
