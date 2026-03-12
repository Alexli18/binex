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

    # Verdict
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

        marker = ""
        if dp and nc.node_id == dp.node_id:
            marker = "  \u2190 root cause"
        elif nc.node_id in downstream_set:
            marker = "  \u2190 affected"

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


def _print_node_details_plain(
    nc, report, cont: str, show_diff: bool,
) -> None:
    """Print nested details under a pipeline node (plain)."""
    # Error message for failed nodes
    if (
        report.error_context
        and report.error_context.node_id == nc.node_id
    ):
        click.echo(
            f"{cont}\u2514\u2500\u2500 "
            f"{report.error_context.error_message}"
        )

    # Content diff or preview for changed nodes
    if nc.content_diff and nc.status == "content_diff":
        if show_diff:
            for line in nc.content_diff:
                click.echo(f"{cont}{line}")
        else:
            good_lines, bad_lines = _extract_preview(
                nc.content_diff,
            )
            if good_lines:
                preview = _content_preview(
                    "\n".join(good_lines), 100,
                )
                click.echo(
                    f"{cont}\u251c\u2500\u2500 "
                    f"good: \"{preview}\""
                )
            if bad_lines:
                preview = _content_preview(
                    "\n".join(bad_lines), 100,
                )
                click.echo(
                    f"{cont}\u2514\u2500\u2500 "
                    f"bad:  \"{preview}\""
                )


def _extract_preview(
    diff_lines: list[str],
) -> tuple[list[str], list[str]]:
    """Extract removed/added lines from unified diff."""
    good: list[str] = []
    bad: list[str] = []
    for line in diff_lines:
        if line.startswith("-") and not line.startswith("---"):
            good.append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
            bad.append(line[1:])
    return good, bad


def _print_footer_plain(report) -> None:
    """Print summary footer line."""
    counts: dict[str, int] = {}
    for nc in report.node_map:
        word = _node_word(nc.status, nc.bad_status)
        counts[word] = counts.get(word, 0) + 1
    parts = [f"{v} {k}" for k, v in counts.items()]
    click.echo(" \u00b7 ".join(parts))


# ---------------------------------------------------------------------------
# Rich output
# ---------------------------------------------------------------------------

def _print_rich(report, show_diff: bool = False) -> None:
    """Print rich formatted bisect output."""
    from binex.cli.ui import get_console, make_panel

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

    # Verdict panel
    if dp is None:
        console.print(make_panel(
            "[green]\u2713 No differences found "
            "\u2014 runs are identical.[/green]",
            title="Verdict",
        ))
    elif dp.divergence_type == "status":
        pattern = ""
        if report.error_context:
            pattern = f" ({report.error_context.pattern})"
        lines = (
            f"[red bold]\u2717 Node \"{dp.node_id}\" "
            f"{dp.bad_status}{pattern}[/red bold]"
        )
        if report.downstream_impact:
            n = len(report.downstream_impact)
            word = "node" if n == 1 else "nodes"
            lines += (
                f"\n  Caused {n} downstream "
                f"{word} to cancel."
            )
        console.print(make_panel(lines, title="Verdict"))
    else:
        desc = _describe_change(dp.similarity)
        lines = (
            f"[yellow bold]\u26a0 Node \"{dp.node_id}\" "
            f"output {desc}[/yellow bold]"
        )
        console.print(make_panel(lines, title="Verdict"))

    console.print()

    # Pipeline
    rich_colors = {
        "match": "green",
        "content_diff": "yellow",
        "status_diff": "red",
        "missing_in_good": "cyan",
        "missing_in_bad": "magenta",
    }

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
        color = rich_colors.get(nc.status, "dim")
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)

        marker = ""
        if dp and nc.node_id == dp.node_id:
            marker = (
                "  [red bold]\u2190 root cause[/red bold]"
            )
        elif nc.node_id in downstream_set:
            marker = "  [dim]\u2190 affected[/dim]"

        console.print(
            f"{connector} [bold]{nc.node_id:<12}[/bold] "
            f"[{color}]{icon} {word:<10}[/{color}] "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        # Error nested
        if (
            report.error_context
            and report.error_context.node_id == nc.node_id
        ):
            console.print(
                f"{cont}\u2514\u2500\u2500 "
                f"[red]{report.error_context.error_message}"
                f"[/red]"
            )

        # Content diff/preview
        if nc.content_diff and nc.status == "content_diff":
            if show_diff:
                for line in nc.content_diff:
                    if (
                        line.startswith("+")
                        and not line.startswith("+++")
                    ):
                        console.print(
                            f"{cont}[green]{line}[/green]"
                        )
                    elif (
                        line.startswith("-")
                        and not line.startswith("---")
                    ):
                        console.print(
                            f"{cont}[red]{line}[/red]"
                        )
                    elif line.startswith("@@"):
                        console.print(
                            f"{cont}[cyan]{line}[/cyan]"
                        )
                    else:
                        console.print(f"{cont}{line}")
            else:
                good_lines, bad_lines = _extract_preview(
                    nc.content_diff,
                )
                if good_lines:
                    preview = _content_preview(
                        "\n".join(good_lines), 100,
                    )
                    console.print(
                        f"{cont}\u251c\u2500\u2500 "
                        f"[green]good: \"{preview}\"[/green]"
                    )
                if bad_lines:
                    preview = _content_preview(
                        "\n".join(bad_lines), 100,
                    )
                    console.print(
                        f"{cont}\u2514\u2500\u2500 "
                        f"[red]bad:  \"{preview}\"[/red]"
                    )

    # Footer
    console.print()
    footer_colors = {
        "ok": "green", "changed": "yellow",
        "failed": "red", "cancelled": "dim",
        "new": "cyan", "missing": "magenta",
        "differs": "red",
    }
    counts: dict[str, int] = {}
    for nc in report.node_map:
        word = _node_word(nc.status, nc.bad_status)
        counts[word] = counts.get(word, 0) + 1
    parts = []
    for k, v in counts.items():
        c = footer_colors.get(k, "")
        if c:
            parts.append(f"[{c}]{v} {k}[/{c}]")
        else:
            parts.append(f"{v} {k}")
    console.print(" \u00b7 ".join(parts))
