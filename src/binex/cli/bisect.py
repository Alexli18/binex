"""CLI `binex bisect` command — find divergence between two runs."""
from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores, has_rich
from binex.cli.bisect_format import (
    _RICH_COLORS,
    _content_preview,
    _describe_change,
    _extract_preview,
    _format_diff_line_rich,
    _format_latency,
    _node_icon,
    _node_word,
    _print_footer_plain,
    _print_node_details_plain,
    _render_footer_rich,
    _render_verdict_rich,
)


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


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
    "--diff", "show_diff",
    is_flag=True, help="Show full unified diffs instead of preview",
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
    show_diff: bool,
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
        _print_rich(report, show_diff)
    else:
        _print_plain(report, show_diff)


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

def _verdict_plain(dp, report) -> None:
    """Print the verdict section in plain text."""
    if dp is None:
        click.echo(
            "\u2713 No differences found "
            "\u2014 runs are identical."
        )
    elif dp.divergence_type == "status":
        pattern = ""
        if report.error_context:
            pattern = f" ({report.error_context.pattern})"
        click.echo(
            f"\u2717 Node \"{dp.node_id}\" "
            f"{dp.bad_status}{pattern}"
        )
        if report.downstream_impact:
            n = len(report.downstream_impact)
            word = "node" if n == 1 else "nodes"
            click.echo(
                f"  Caused {n} downstream {word} to cancel."
            )
    else:
        desc = _describe_change(dp.similarity)
        click.echo(f"\u26a0 Node \"{dp.node_id}\" output {desc}")


def _node_marker_plain(nc, dp, downstream_set) -> str:
    """Return the marker suffix for a pipeline node."""
    if dp and nc.node_id == dp.node_id:
        return "  \u2190 root cause"
    if nc.node_id in downstream_set:
        return "  \u2190 affected"
    return ""


def _print_plain(report, show_diff: bool = False) -> None:
    """Print intuitive plain text bisect output."""
    # Header
    click.echo(f"Bisect: {report.workflow_name}")
    click.echo(
        f"good {report.good_run_id}  vs  bad {report.bad_run_id}"
    )
    click.echo()

    dp = report.divergence_point
    downstream_set = set(report.downstream_impact)

    _verdict_plain(dp, report)
    click.echo()

    # Pipeline
    click.echo("Pipeline")
    total = len(report.node_map)
    for i, nc in enumerate(report.node_map):
        is_last = i == total - 1
        connector = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"
        cont = "   " if is_last else "\u2502  "

        icon = _node_icon(nc.status)
        word = _node_word(nc.status, nc.bad_status)
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)
        marker = _node_marker_plain(nc, dp, downstream_set)

        click.echo(
            f"{connector} {nc.node_id:<12} "
            f"{icon} {word:<10} "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        # Nested details
        _print_node_details_plain(nc, report, cont, show_diff)

    # Footer
    click.echo()
    _print_footer_plain(report)


# ---------------------------------------------------------------------------
# Rich output
# ---------------------------------------------------------------------------

def _node_marker_rich(nc, dp, downstream_set) -> str:
    """Return the Rich marker suffix for a pipeline node."""
    if dp and nc.node_id == dp.node_id:
        return "  [red bold]\u2190 root cause[/red bold]"
    if nc.node_id in downstream_set:
        return "  [dim]\u2190 affected[/dim]"
    return ""


def _print_node_error_rich(console, nc, report, cont: str) -> None:
    """Print error context for a node in Rich format."""
    if (
        report.error_context
        and report.error_context.node_id == nc.node_id
    ):
        console.print(
            f"{cont}\u2514\u2500\u2500 "
            f"[red]{report.error_context.error_message}"
            f"[/red]"
        )


def _print_node_diff_rich(console, nc, cont: str, show_diff: bool) -> None:
    """Print content diff or preview for a node in Rich format."""
    if not (nc.content_diff and nc.status == "content_diff"):
        return
    if show_diff:
        for line in nc.content_diff:
            formatted = _format_diff_line_rich(line)
            console.print(f"{cont}{formatted}")
    else:
        good_lines, bad_lines = _extract_preview(nc.content_diff)
        if good_lines:
            preview = _content_preview("\n".join(good_lines), 100)
            console.print(
                f"{cont}\u251c\u2500\u2500 "
                f"[green]good: \"{preview}\"[/green]"
            )
        if bad_lines:
            preview = _content_preview("\n".join(bad_lines), 100)
            console.print(
                f"{cont}\u2514\u2500\u2500 "
                f"[red]bad:  \"{preview}\"[/red]"
            )


def _print_rich(report, show_diff: bool = False) -> None:
    """Print rich formatted bisect output."""
    from binex.cli.ui import get_console

    console = get_console()

    dp = report.divergence_point
    downstream_set = set(report.downstream_impact)

    # Header
    console.print(
        f"[bold]Bisect:[/bold] {report.workflow_name}"
    )
    console.print(
        f"[cyan]good[/cyan] {report.good_run_id}  vs  "
        f"[cyan]bad[/cyan] {report.bad_run_id}"
    )
    console.print()

    # Verdict
    _render_verdict_rich(console, report, dp)
    console.print()

    # Pipeline
    console.print("[bold]Pipeline[/bold]")
    total = len(report.node_map)
    for i, nc in enumerate(report.node_map):
        is_last = i == total - 1
        connector = (
            "\u2514\u2500\u2500" if is_last
            else "\u251c\u2500\u2500"
        )
        cont = "   " if is_last else "\u2502  "

        icon = _node_icon(nc.status)
        word = _node_word(nc.status, nc.bad_status)
        color = _RICH_COLORS.get(nc.status, "dim")
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)
        marker = _node_marker_rich(nc, dp, downstream_set)

        console.print(
            f"{connector} [bold]{nc.node_id:<12}[/bold] "
            f"[{color}]{icon} {word:<10}[/{color}] "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        _print_node_error_rich(console, nc, report, cont)
        _print_node_diff_rich(console, nc, cont, show_diff)

    # Footer
    console.print()
    _render_footer_rich(console, report)
