"""CLI `binex diagnose` command — root-cause analysis."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores, has_rich


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.command("diagnose")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
def diagnose_cmd(run_id: str, json_out: bool, rich_out: bool | None) -> None:
    """Analyze a run and identify root causes of failure."""
    if rich_out is None:
        rich_out = has_rich()
    try:
        report = asyncio.run(_run_diagnose(run_id))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from binex.trace.diagnose import report_to_dict

    result = report_to_dict(report)

    if json_out:
        click.echo(json.dumps(result, default=str, indent=2))
    elif rich_out:
        _print_rich(report)
    else:
        _print_plain(report)


async def _run_diagnose(run_id: str):
    from binex.trace.diagnose import diagnose_run

    exec_store, art_store = _get_stores()
    try:
        return await diagnose_run(exec_store, art_store, run_id)
    finally:
        await exec_store.close()


def _print_plain(report) -> None:
    """Print plain text diagnose output."""
    click.echo(f"Run: {report.run_id}")
    click.echo(f"Status: {report.status}")
    if report.root_cause:
        click.echo(f"\nRoot Cause: {report.root_cause.node_id}")
        click.echo(f"  Error: {report.root_cause.error_message}")
        click.echo(f"  Pattern: {report.root_cause.pattern}")
    if report.affected_nodes:
        click.echo(f"\nAffected Nodes: {', '.join(report.affected_nodes)}")
    if report.latency_anomalies:
        click.echo("\nLatency Anomalies:")
        for a in report.latency_anomalies:
            click.echo(f"  {a.node_id}: {a.latency_ms:.0f}ms ({a.ratio:.1f}x median)")
    if report.recommendations:
        click.echo("\nRecommendations:")
        for r in report.recommendations:
            click.echo(f"  - {r}")


def _print_rich(report) -> None:
    """Print rich formatted diagnose output."""
    from rich.table import Table

    from binex.cli.ui import get_console, make_panel

    console = get_console()

    # Header
    status_style = "red bold" if report.status == "issues_found" else "green bold"
    console.print(make_panel(
        f"[bold]Run:[/bold] [cyan]{report.run_id}[/cyan]\n"
        f"[bold]Status:[/bold] [{status_style}]{report.status}[/{status_style}]",
        title="Diagnostic Report",
    ))

    if report.root_cause:
        console.print(make_panel(
            f"[bold]Node:[/bold] {report.root_cause.node_id}\n"
            f"[bold]Error:[/bold] {report.root_cause.error_message}\n"
            f"[bold]Pattern:[/bold] {report.root_cause.pattern}",
            title="Root Cause",
        ))

    if report.affected_nodes:
        console.print(make_panel(
            ", ".join(report.affected_nodes),
            title=f"Affected Nodes ({len(report.affected_nodes)})",
        ))

    if report.latency_anomalies:
        table = Table(title="Latency Anomalies")
        table.add_column("Node", style="bold")
        table.add_column("Latency", justify="right")
        table.add_column("Median", justify="right")
        table.add_column("Ratio", justify="right")
        for a in report.latency_anomalies:
            table.add_row(
                a.node_id,
                f"{a.latency_ms:.0f}ms",
                f"{a.median_ms:.0f}ms",
                f"{a.ratio:.1f}x",
            )
        console.print(table)

    if report.recommendations:
        rec_text = "\n".join(f"\u2022 {r}" for r in report.recommendations)
        console.print(make_panel(rec_text, title="Recommendations"))
