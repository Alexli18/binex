"""CLI `binex bisect` command — find divergence between two runs."""
from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores, has_rich


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _content_preview(text: str | None, limit: int = 100) -> str:
    """First line of text, truncated to limit chars."""
    if not text:
        return ""
    first_line = text.split("\n", 1)[0]
    if len(first_line) <= limit:
        return first_line
    return first_line[:limit] + "\u2026"


def _describe_change(similarity: float | None) -> str:
    """Human-readable description of content change."""
    if similarity is None:
        return "changed"
    if similarity < 0.3:
        return "completely changed"
    if similarity < 0.7:
        return "partially changed"
    return "slightly changed"


def _format_latency(ms: int | None) -> str:
    """Format latency for display."""
    if ms is None:
        return "-"
    if ms == 0:
        return "skipped"
    if ms >= 10000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"


_NODE_ICONS = {
    "match": "\u2713",
    "content_diff": "\u26a0",
    "status_diff": "\u2717",
    "missing_in_good": "?",
    "missing_in_bad": "?",
}

_NODE_WORDS: dict[str, str | dict[str, str]] = {
    "match": "ok",
    "content_diff": "changed",
    "status_diff": {
        "failed": "failed",
        "cancelled": "cancelled",
        "_default": "differs",
    },
    "missing_in_good": "new",
    "missing_in_bad": "missing",
}


def _node_icon(status: str) -> str:
    """Get icon for node status."""
    return _NODE_ICONS.get(status, "?")


def _node_word(status: str, bad_status: str | None = None) -> str:
    """Get human-readable word for node status."""
    word = _NODE_WORDS.get(status, "unknown")
    if isinstance(word, dict):
        return word.get(bad_status or "", word["_default"])
    return word


@click.command("bisect")
@click.argument("good_run_id")
@click.argument("bad_run_id")
@click.option(
    "--threshold", type=float, default=0.9,
    help="Content similarity threshold (0.0-1.0)",
)
@click.option(
    "--json-output", "--json", "json_out",
    is_flag=True, help="Output as JSON",
)
@click.option(
    "--rich/--no-rich", "rich_out",
    default=None, help="Rich output (auto-detected)",
)
def bisect_cmd(
    good_run_id: str,
    bad_run_id: str,
    threshold: float,
    json_out: bool,
    rich_out: bool | None,
) -> None:
    """Find the first node where two runs diverge."""
    if rich_out is None:
        rich_out = has_rich()
    try:
        report = asyncio.run(
            _run_bisect(good_run_id, bad_run_id, threshold),
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from binex.trace.bisect import bisect_report_to_dict

    result = bisect_report_to_dict(report)

    if json_out:
        click.echo(json.dumps(result, default=str, indent=2))
    elif rich_out:
        _print_rich(report)
    else:
        _print_plain(report)


async def _run_bisect(
    good_run_id: str, bad_run_id: str, threshold: float,
):
    from binex.trace.bisect import bisect_report

    exec_store, art_store = _get_stores()
    try:
        return await bisect_report(
            exec_store, art_store,
            good_run_id, bad_run_id, threshold,
        )
    finally:
        await exec_store.close()


# ---------------------------------------------------------------------------
# Plain text output
# ---------------------------------------------------------------------------

def _print_plain(report) -> None:
    """Print plain text bisect output."""
    click.echo(f"Good Run: {report.good_run_id}")
    click.echo(f"Bad Run:  {report.bad_run_id}")
    click.echo(f"Workflow: {report.workflow_name}")

    # Summary
    match_count = sum(
        1 for nc in report.node_map if nc.status == "match"
    )
    diff_count = len(report.node_map) - match_count
    click.echo(
        f"Nodes: {match_count} match, {diff_count} differ"
    )

    dp = report.divergence_point
    if dp is None:
        click.echo("\nNo divergence found — runs are identical.")
        return

    # Divergence point
    click.echo(f"\nDivergence at: {dp.node_id}")
    click.echo(f"  Type: {dp.divergence_type}")
    if dp.similarity is not None:
        click.echo(f"  Similarity: {dp.similarity:.1%}")
    click.echo(f"  Good status: {dp.good_status}")
    click.echo(f"  Bad status:  {dp.bad_status}")
    if dp.upstream_context:
        click.echo(
            f"  Upstream: {', '.join(dp.upstream_context)}"
        )

    # Error context
    if report.error_context:
        ec = report.error_context
        click.echo(f"\nError: {ec.error_message}")
        click.echo(f"  Pattern: {ec.pattern}")

    # Per-node content diffs
    for nc in report.node_map:
        if nc.content_diff:
            click.echo(f"\nContent Diff [{nc.node_id}]:")
            for line in nc.content_diff:
                click.echo(f"  {line}")

    # Downstream impact
    if report.downstream_impact:
        click.echo(
            f"\nDownstream Impact: "
            f"{', '.join(report.downstream_impact)} "
            f"({len(report.downstream_impact)} nodes)"
        )

    # Node map
    click.echo("\nNode Map:")
    for nc in report.node_map:
        icon = "+" if nc.status == "match" else "!"
        lat_good = (
            f"{nc.latency_good_ms}ms" if nc.latency_good_ms else "-"
        )
        lat_bad = (
            f"{nc.latency_bad_ms}ms" if nc.latency_bad_ms else "-"
        )
        click.echo(
            f"  {icon} {nc.node_id:<20} "
            f"{nc.status:<15} {lat_good} / {lat_bad}"
        )


# ---------------------------------------------------------------------------
# Rich output
# ---------------------------------------------------------------------------

def _print_rich(report) -> None:
    """Print rich formatted bisect output."""
    from rich.table import Table

    from binex.cli.ui import get_console, make_panel

    console = get_console()

    # Summary header
    match_count = sum(
        1 for nc in report.node_map if nc.status == "match"
    )
    diff_count = len(report.node_map) - match_count
    console.print(make_panel(
        f"[bold]Good Run:[/bold] [cyan]{report.good_run_id}[/cyan]\n"
        f"[bold]Bad Run:[/bold]  [cyan]{report.bad_run_id}[/cyan]\n"
        f"[bold]Workflow:[/bold] {report.workflow_name}\n"
        f"[bold]Nodes:[/bold] "
        f"[green]{match_count} match[/green], "
        f"[yellow]{diff_count} differ[/yellow]",
        title="Run Bisect",
    ))

    dp = report.divergence_point
    if dp is None:
        console.print(make_panel(
            "[green]No divergence found — runs are identical.[/green]",
            title="Result",
        ))
        return

    # Divergence point
    sim_text = ""
    if dp.similarity is not None:
        sim_text = (
            f"\n[bold]Similarity:[/bold] {dp.similarity:.1%}"
        )
    upstream_text = ""
    if dp.upstream_context:
        upstream_text = (
            f"\n[bold]Upstream:[/bold] "
            f"{', '.join(dp.upstream_context)}"
        )
    style = (
        "red" if dp.divergence_type == "status" else "yellow"
    )
    console.print(make_panel(
        f"[bold]Node:[/bold] [{style}]{dp.node_id}[/{style}]\n"
        f"[bold]Type:[/bold] {dp.divergence_type}\n"
        f"[bold]Good:[/bold] {dp.good_status}\n"
        f"[bold]Bad:[/bold]  {dp.bad_status}"
        f"{sim_text}{upstream_text}",
        title="Divergence Point",
    ))

    # Error context
    if report.error_context:
        ec = report.error_context
        console.print(make_panel(
            f"[bold]Error:[/bold] {ec.error_message}\n"
            f"[bold]Pattern:[/bold] {ec.pattern}",
            title="Error Context",
        ))

    # Per-node content diffs
    for nc in report.node_map:
        if nc.content_diff:
            diff_lines = []
            for line in nc.content_diff:
                if line.startswith("+") and not line.startswith("+++"):
                    diff_lines.append(f"[green]{line}[/green]")
                elif line.startswith("-") and not line.startswith("---"):
                    diff_lines.append(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    diff_lines.append(f"[cyan]{line}[/cyan]")
                else:
                    diff_lines.append(line)
            console.print(make_panel(
                "\n".join(diff_lines),
                title=f"Content Diff — {nc.node_id}",
            ))

    # Downstream impact
    if report.downstream_impact:
        console.print(make_panel(
            ", ".join(report.downstream_impact),
            title=(
                f"Downstream Impact "
                f"({len(report.downstream_impact)} nodes)"
            ),
        ))

    # Node map table
    table = Table(title="Node Map")
    table.add_column("Node", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Good", justify="center")
    table.add_column("Bad", justify="center")
    table.add_column("Latency Good", justify="right")
    table.add_column("Latency Bad", justify="right")

    status_styles = {
        "match": "green",
        "status_diff": "red",
        "content_diff": "yellow",
        "missing_in_good": "magenta",
        "missing_in_bad": "magenta",
    }

    for nc in report.node_map:
        st_style = status_styles.get(nc.status, "dim")
        lat_g = (
            f"{nc.latency_good_ms}ms"
            if nc.latency_good_ms is not None else "-"
        )
        lat_b = (
            f"{nc.latency_bad_ms}ms"
            if nc.latency_bad_ms is not None else "-"
        )
        table.add_row(
            nc.node_id,
            f"[{st_style}]{nc.status}[/{st_style}]",
            nc.good_status or "-",
            nc.bad_status or "-",
            lat_g,
            lat_b,
        )

    console.print(table)
