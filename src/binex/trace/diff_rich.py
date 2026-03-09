"""Rich-formatted diff output."""

from __future__ import annotations

import io
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def format_diff_rich(diff_result: dict[str, Any]) -> str:
    """Render a diff result with rich formatting."""
    console = Console(record=True, file=io.StringIO(), width=100)

    run_a = diff_result["run_a"]
    run_b = diff_result["run_b"]
    status_a = diff_result["status_a"]
    status_b = diff_result["status_b"]

    # Header
    sa_color = "green" if status_a == "completed" else "red"
    sb_color = "green" if status_b == "completed" else "red"
    console.print(Panel(
        f"[bold]Workflow:[/bold] {diff_result['workflow_a']}\n"
        f"[bold]Run A:[/bold] [cyan]{run_a}[/cyan] "
        f"[{sa_color}]{status_a}[/{sa_color}]\n"
        f"[bold]Run B:[/bold] [cyan]{run_b}[/cyan] "
        f"[{sb_color}]{status_b}[/{sb_color}]",
        title="[bold]Run Diff[/bold]",
        border_style="blue",
    ))

    # Diff table
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Node", style="bold")
    table.add_column("Status A", justify="center")
    table.add_column("Status B", justify="center")
    table.add_column("Latency A", justify="right")
    table.add_column("Latency B", justify="right")
    table.add_column("Changes")

    for step in diff_result["steps"]:
        changes = []
        row_style = ""

        if step["agent_changed"]:
            changes.append(
                f"agent: {step['agent_a']} -> {step['agent_b']}"
            )
        if step["artifacts_changed"]:
            changes.append("[yellow]artifacts changed[/yellow]")
        if step["status_changed"]:
            row_style = "yellow"

        # Status styling
        sa = step["status_a"] or "-"
        sb = step["status_b"] or "-"
        sa_style = "green" if sa == "completed" else "red" if sa == "failed" else "dim"
        sb_style = "green" if sb == "completed" else "red" if sb == "failed" else "dim"

        # Latency with delta
        lat_a = f"{step['latency_a']}ms" if step["latency_a"] is not None else "-"
        lat_b = f"{step['latency_b']}ms" if step["latency_b"] is not None else "-"
        if (step["latency_a"] is not None and step["latency_b"] is not None):
            delta = step["latency_b"] - step["latency_a"]
            sign = "+" if delta >= 0 else ""
            d_color = "red" if delta > 0 else "green"
            lat_b = f"{step['latency_b']}ms [{d_color}]({sign}{delta}ms)[/{d_color}]"

        # Error info
        if step.get("error_a") and not step.get("error_b"):
            changes.append("[green]error resolved[/green]")
        elif not step.get("error_a") and step.get("error_b"):
            changes.append(f"[red]new error: {step['error_b'][:30]}[/red]")

        table.add_row(
            step["task_id"],
            Text(sa, style=sa_style),
            Text(sb, style=sb_style),
            lat_a,
            lat_b,
            " | ".join(changes) if changes else "[dim]no changes[/dim]",
            style=row_style,
        )

    console.print(table)
    return console.export_text()
