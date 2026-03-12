"""Rich-formatted diff output."""

from __future__ import annotations

import difflib
from typing import Any

from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from binex.cli.ui import STATUS_CONFIG, get_console, make_panel, make_table


def _format_latency_delta(
    lat_a_val: int | None, lat_b_val: int | None,
) -> tuple[str, str]:
    """Format latency values with delta coloring.

    Returns (lat_a_str, lat_b_str) ready for display.
    """
    lat_a = f"{lat_a_val}ms" if lat_a_val is not None else "-"
    lat_b = f"{lat_b_val}ms" if lat_b_val is not None else "-"
    if lat_a_val is not None and lat_b_val is not None:
        delta = lat_b_val - lat_a_val
        sign = "+" if delta >= 0 else ""
        d_color = "red" if delta > 0 else "green"
        lat_b = f"{lat_b_val}ms [{d_color}]({sign}{delta}ms)[/{d_color}]"
    return lat_a, lat_b


def _detect_error_changes(error_a: str | None, error_b: str | None) -> str | None:
    """Detect error resolution or new errors between two runs.

    Returns a rich-formatted change string, or None if no error change.
    """
    if error_a and not error_b:
        return "[green]error resolved[/green]"
    if not error_a and error_b:
        return f"[red]new error: {error_b[:30]}[/red]"
    return None


def _build_diff_row(step: dict[str, Any]) -> tuple[list[str], str, str, str, str, str]:
    """Build a single diff table row. Returns (changes, sa, sb, lat_a, lat_b, row_style)."""
    changes: list[str] = []
    row_style = ""

    if step["agent_changed"]:
        changes.append(f"agent: {step['agent_a']} -> {step['agent_b']}")
    if step["artifacts_changed"]:
        changes.append("[yellow]artifacts changed[/yellow]")
    if step["status_changed"]:
        row_style = "yellow"

    lat_a, lat_b = _format_latency_delta(step["latency_a"], step["latency_b"])

    error_change = _detect_error_changes(step.get("error_a"), step.get("error_b"))
    if error_change:
        changes.append(error_change)

    sa = step["status_a"] or "-"
    sb = step["status_b"] or "-"
    return changes, sa, sb, lat_a, lat_b, row_style


def _get_status_style(status: str) -> str:
    """Get the style string for a status from the shared config."""
    return STATUS_CONFIG.get(status, ("unknown", "dim"))[1]


def _render_summary(console, summary: dict) -> None:
    """Render diff summary statistics."""
    table = Table(title="Summary", show_header=False, box=None)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Nodes", str(summary["total_nodes"]))
    table.add_row("Changed", f"[yellow]{summary['changed_nodes']}[/yellow]")
    table.add_row("Unchanged", f"[green]{summary['unchanged_nodes']}[/green]")

    delta = summary["latency_delta_ms"]
    sign = "+" if delta >= 0 else ""
    color = "red" if delta > 0 else "green"
    table.add_row("Latency Delta", f"[{color}]{sign}{delta:.0f}ms[/{color}]")

    sim = summary["content_similarity"]
    sim_color = "green" if sim > 0.9 else "yellow" if sim > 0.5 else "red"
    table.add_row("Content Similarity", f"[{sim_color}]{sim:.1%}[/{sim_color}]")

    console.print(table)
    console.print()


def _render_side_by_side(console, step: dict) -> None:
    """Render side-by-side content panels for a changed node."""
    content_a = step.get("content_a") or "(no content)"
    content_b = step.get("content_b") or "(no content)"

    # Highlight differences using difflib.ndiff
    if step.get("content_a") and step.get("content_b"):
        diff_lines = list(difflib.ndiff(
            content_a.splitlines(keepends=True),
            content_b.splitlines(keepends=True),
        ))
        # Show changed lines highlighted
        highlighted_b = []
        for line in diff_lines:
            if line.startswith("+ "):
                highlighted_b.append(f"[green]{line[2:].rstrip()}[/green]")
            elif line.startswith("- "):
                pass  # skip removals in B panel
            elif line.startswith("  "):
                highlighted_b.append(line[2:].rstrip())
        content_b_display = "\n".join(highlighted_b) if highlighted_b else content_b
    else:
        content_b_display = content_b

    sim = step.get("content_similarity", 0)

    panels = Columns([
        Panel(content_a[:500], title="Run A", border_style="blue"),
        Panel(content_b_display[:500], title=f"Run B ({sim:.0%} similar)", border_style="yellow"),
    ], equal=True)

    console.print(f"\n[bold]{step['task_id']}[/bold]")
    console.print(panels)


def format_diff_rich(diff_result: dict[str, Any]) -> None:
    """Print a diff result with rich formatting directly to the terminal."""
    console = get_console()

    run_a = diff_result["run_a"]
    run_b = diff_result["run_b"]
    status_a = diff_result["status_a"]
    status_b = diff_result["status_b"]

    style_a = _get_status_style(status_a)
    style_b = _get_status_style(status_b)

    console.print(make_panel(
        f"[bold]Workflow:[/bold] {diff_result['workflow_a']}\n"
        f"[bold]Run A:[/bold] [cyan]{run_a}[/cyan] "
        f"[{style_a}]{status_a}[/{style_a}]\n"
        f"[bold]Run B:[/bold] [cyan]{run_b}[/cyan] "
        f"[{style_b}]{status_b}[/{style_b}]",
        title="Run Diff",
    ))

    # Summary table
    if "summary" in diff_result:
        _render_summary(console, diff_result["summary"])

    table = make_table(
        ("Node", {"style": "bold"}),
        ("Status A", {"justify": "center"}),
        ("Status B", {"justify": "center"}),
        ("Latency A", {"justify": "right"}),
        ("Latency B", {"justify": "right"}),
        ("Changes", {}),
    )

    for step in diff_result["steps"]:
        changes, sa, sb, lat_a, lat_b, row_style = _build_diff_row(step)
        table.add_row(
            step["task_id"],
            Text(sa, style=_get_status_style(sa)),
            Text(sb, style=_get_status_style(sb)),
            lat_a,
            lat_b,
            " | ".join(changes) if changes else "[dim]no changes[/dim]",
            style=row_style,
        )

    console.print(table)

    # Side-by-side panels for changed nodes
    for step in diff_result["steps"]:
        if step.get("artifacts_changed") and (step.get("content_a") or step.get("content_b")):
            _render_side_by_side(console, step)
