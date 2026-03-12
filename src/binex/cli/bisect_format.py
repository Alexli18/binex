"""Formatting helpers for `binex bisect` output."""
from __future__ import annotations

import click

# ---------------------------------------------------------------------------
# Content & latency helpers
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


# ---------------------------------------------------------------------------
# Node icon / word helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Diff preview extraction
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Plain text helpers
# ---------------------------------------------------------------------------

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


def _print_footer_plain(report) -> None:
    """Print summary footer line."""
    counts: dict[str, int] = {}
    for nc in report.node_map:
        word = _node_word(nc.status, nc.bad_status)
        counts[word] = counts.get(word, 0) + 1
    parts = [f"{v} {k}" for k, v in counts.items()]
    click.echo(" \u00b7 ".join(parts))


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

_RICH_COLORS = {
    "match": "green",
    "content_diff": "yellow",
    "status_diff": "red",
    "missing_in_good": "cyan",
    "missing_in_bad": "magenta",
}

_FOOTER_COLORS = {
    "ok": "green", "changed": "yellow",
    "failed": "red", "cancelled": "dim",
    "new": "cyan", "missing": "magenta",
    "differs": "red",
}


def _render_verdict_rich(console, report, dp) -> None:
    """Render the verdict panel in Rich format."""
    from binex.cli.ui import make_panel

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


def _format_diff_line_rich(line: str) -> str:
    """Classify a unified diff line and return Rich-formatted string."""
    if line.startswith("+") and not line.startswith("+++"):
        return f"[green]{line}[/green]"
    if line.startswith("-") and not line.startswith("---"):
        return f"[red]{line}[/red]"
    if line.startswith("@@"):
        return f"[cyan]{line}[/cyan]"
    return line


def _render_footer_rich(console, report) -> None:
    """Render footer statistics in Rich format."""
    counts: dict[str, int] = {}
    for nc in report.node_map:
        word = _node_word(nc.status, nc.bad_status)
        counts[word] = counts.get(word, 0) + 1
    parts = []
    for k, v in counts.items():
        c = _FOOTER_COLORS.get(k, "")
        if c:
            parts.append(f"[{c}]{v} {k}[/{c}]")
        else:
            parts.append(f"{v} {k}")
    console.print(" \u00b7 ".join(parts))
