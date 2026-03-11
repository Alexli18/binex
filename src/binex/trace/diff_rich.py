"""Rich-formatted diff output."""

from __future__ import annotations

from typing import Any

from rich.text import Text

from binex.cli.ui import STATUS_CONFIG, get_console, make_panel, make_table


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

    # Latency with delta
    lat_a = f"{step['latency_a']}ms" if step["latency_a"] is not None else "-"
    lat_b = f"{step['latency_b']}ms" if step["latency_b"] is not None else "-"
    if step["latency_a"] is not None and step["latency_b"] is not None:
        delta = step["latency_b"] - step["latency_a"]
        sign = "+" if delta >= 0 else ""
        d_color = "red" if delta > 0 else "green"
        lat_b = f"{step['latency_b']}ms [{d_color}]({sign}{delta}ms)[/{d_color}]"

    # Error info
    if step.get("error_a") and not step.get("error_b"):
        changes.append("[green]error resolved[/green]")
    elif not step.get("error_a") and step.get("error_b"):
        changes.append(f"[red]new error: {step['error_b'][:30]}[/red]")

    sa = step["status_a"] or "-"
    sb = step["status_b"] or "-"
    return changes, sa, sb, lat_a, lat_b, row_style


def _get_status_style(status: str) -> str:
    """Get the style string for a status from the shared config."""
    return STATUS_CONFIG.get(status, ("unknown", "dim"))[1]


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
