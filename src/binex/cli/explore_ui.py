"""Explore UI rendering — dashboard, node detail, artifacts, diagnose."""

from __future__ import annotations

import json

import click

from binex.cli import has_rich
from binex.cli.explore_utils import _preview, _short_id, _time_ago
from binex.trace.lineage import build_lineage_tree, format_lineage_tree


def _render_dashboard(run, records, run_id: str, cost_records=None) -> None:
    """Render dashboard panel with header, status, and node table."""
    node_costs: dict[str, float] = {}
    for cr in (cost_records or []):
        node_costs[cr.task_id] = node_costs.get(cr.task_id, 0.0) + cr.cost

    if has_rich():
        _render_dashboard_rich(run, records, run_id, node_costs)
    else:
        _render_dashboard_plain(run, records, run_id, node_costs)


def _render_dashboard_rich(run, records, run_id: str, node_costs: dict) -> None:
    """Render dashboard with Rich formatting."""
    from rich.console import Group as RichGroup
    from rich.text import Text

    from binex.cli.ui import (
        STATUS_CONFIG,
        get_console,
        make_header,
        make_panel,
        make_table,
        status_text,
    )

    header = make_header(run=_short_id(run_id), workflow=run.workflow_name)

    _, st_style = STATUS_CONFIG.get(run.status, (run.status, "dim"))
    status_line = Text()
    status_line.append("Status: ", style="dim")
    status_line.append(run.status, style=st_style)
    status_line.append(
        f"  ·  Nodes: {run.completed_nodes}/{run.total_nodes}", style="dim",
    )
    if run.total_cost:
        status_line.append(f"  ·  Cost: ${run.total_cost:.4f}", style="cyan")
    status_line.append(f"  ·  {_time_ago(run.started_at)}", style="dim")

    table = make_table(
        ("Node", {"style": "bold", "min_width": 14}),
        ("Status", {"min_width": 10}),
        ("Agent", {"style": "dim"}),
        ("Cost", {"justify": "right"}),
        ("Latency", {"justify": "right"}),
    )
    for rec in records:
        latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
        nc = node_costs.get(rec.task_id)
        cost_str = f"${nc:.4f}" if nc else ""
        table.add_row(
            rec.task_id, status_text(rec.status.value),
            rec.agent_id, cost_str, latency,
        )

    panel = make_panel(
        RichGroup(header, Text(), status_line, Text(), table),
        title="Dashboard", subtitle=f"run: {run_id}",
    )
    get_console().print(panel)


def _render_dashboard_plain(run, records, run_id: str, node_costs: dict) -> None:
    """Render dashboard in plain text."""
    click.echo(f"  === Dashboard: {_short_id(run_id)} ===")
    click.echo(f"  Workflow: {run.workflow_name}")
    cost_str = f"Cost: ${run.total_cost:.4f}  " if run.total_cost else ""
    click.echo(
        f"  Status: {run.status}  "
        f"Nodes: {run.completed_nodes}/{run.total_nodes}  "
        f"{cost_str}"
        f"{_time_ago(run.started_at)}"
    )
    click.echo()
    if records:
        click.echo("  Nodes:")
        for rec in records:
            latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
            nc = node_costs.get(rec.task_id)
            nc_str = f"${nc:.4f}" if nc else ""
            click.echo(
                f"    {rec.task_id:<20} {rec.status.value:<12} "
                f"{rec.agent_id:<20} {nc_str:<10} {latency}"
            )
    else:
        click.echo("  (no execution records)")
    click.echo()


def _print_dashboard_menu() -> None:
    """Print action key hints."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        hint = Text()
        for key, label in [
            ("t", "trace"), ("g", "graph"), ("d", "debug"),
            ("c", "cost"), ("a", "artifacts"), ("n", "node"),
            ("r", "replay"), ("i", "diagnose"), ("f", "diff"),
            ("b", "bisect"), ("q", "back"), ("Q", "quit"),
        ]:
            hint.append("  [", style="dim")
            hint.append(key, style="cyan bold")
            hint.append(f"] {label}", style="dim")
        get_console().print(hint)
    else:
        click.echo(
            "  [t]race [g]raph [d]ebug [c]ost [a]rtifacts [n]ode"
            " [r]eplay [i] d[i]agnose [f] dif[f] [b]isect [q] back [Q] quit"
        )


def _wait_for_enter() -> bool:
    """Prompt user to press Enter or q. Returns True to leave dashboard."""
    choice = click.prompt(
        "  [Enter] back to dashboard · [q] back to runs", default="",
    )
    return choice.strip().lower() == "q"


def _wait_for_enter_or_preview(node_arts: list) -> bool:
    """Prompt with preview option for node detail. Returns True to leave dashboard."""
    while True:
        choice = click.prompt(
            "  [Enter] back · [p] full preview · [q] back to runs", default="",
        )
        key = choice.strip().lower()
        if key == "q":
            return True
        if key == "p":
            _show_full_preview(node_arts)
            continue
        return False


def _show_full_preview(node_arts: list) -> None:
    """Render full artifact content as Rich Markdown panels."""
    if not node_arts:
        click.echo("  No artifacts to preview.")
        return

    for art in node_arts:
        content = art.content if art.content is not None else ""
        if not isinstance(content, str):
            content = json.dumps(content, default=str, indent=2)
        node = art.lineage.produced_by if art.lineage else "?"

        click.echo()
        if has_rich():
            from rich.markdown import Markdown

            from binex.cli.ui import get_console, make_panel

            console = get_console()
            console.print(make_panel(
                Markdown(content),
                title=f"[bold]{node}[/bold] / {art.type}",
                subtitle=f"id: {art.id}",
            ))
        else:
            click.echo(f"  ── {node} / {art.type} ──")
            click.echo(f"  {content}")
            click.echo(f"  id: {art.id}")


def _print_artifacts_table(artifacts, run_id: str) -> None:
    """Display artifacts as a table (rich or plain)."""
    if has_rich():
        from binex.cli.ui import get_console, make_table

        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Node", {"style": "magenta", "min_width": 16}),
            ("Type", {"style": "yellow", "min_width": 10}),
            ("Preview", {"min_width": 30}),
            title=f"Artifacts — {_short_id(run_id)}",
        )

        for i, art in enumerate(artifacts, 1):
            node = art.lineage.produced_by if art.lineage else "?"
            table.add_row(str(i), node, art.type, _preview(art.content, max_len=60))
        get_console().print(table)
    else:
        click.echo(f"  Artifacts for {_short_id(run_id)}:")
        click.echo()
        for i, art in enumerate(artifacts, 1):
            node = art.lineage.produced_by if art.lineage else "?"
            click.echo(
                f"  {i:>3})  {node:<20} {art.type:<12} {_preview(art.content)}"
            )


def _show_artifact_detail(artifact) -> None:
    """Render artifact detail."""
    content_str = artifact.content if artifact.content is not None else ""
    if not isinstance(content_str, str):
        content_str = json.dumps(content_str, default=str, indent=2)

    node = artifact.lineage.produced_by if artifact.lineage else "?"

    if has_rich():
        from rich.markdown import Markdown
        from rich.text import Text

        from binex.cli.ui import STATUS_CONFIG, get_console, make_panel

        console = get_console()
        meta = Text()
        meta.append("Node: ", style="dim")
        meta.append(node, style="magenta bold")
        meta.append("  Type: ", style="dim")
        meta.append(artifact.type, style="yellow")
        meta.append("  Status: ", style="dim")
        _, style = STATUS_CONFIG.get(artifact.status, (artifact.status, "dim"))
        meta.append(artifact.status, style=style)
        console.print(meta)
        console.print()
        console.print(make_panel(
            Markdown(content_str),
            title=f"{node} / {artifact.type}",
            subtitle=f"id: {artifact.id}",
        ))
    else:
        click.echo(f"  -- {node} / {artifact.type} --")
        click.echo(f"  {content_str}")
        click.echo(f"  id: {artifact.id}")
        click.echo()


async def _show_lineage(art_store, artifact_id: str) -> None:
    """Display artifact lineage tree."""
    tree = await build_lineage_tree(art_store, artifact_id)
    if not tree:
        click.echo("  No lineage data available.")
        return

    click.echo()
    if has_rich():
        from rich.tree import Tree as RichTree

        from binex.cli.ui import get_console, make_panel

        def _build_rich_tree(node, parent=None):
            label = (
                f"[magenta bold]{node['produced_by']}[/] "
                f"[dim]({node['artifact_id']})[/] "
                f"[yellow]{node['type']}[/]"
            )
            if parent is None:
                branch = RichTree(label, guide_style="cyan")
            else:
                branch = parent.add(label)
            for p in node["parents"]:
                _build_rich_tree(p, branch)
            return branch

        rich_tree = _build_rich_tree(tree)
        get_console().print(make_panel(rich_tree, title="Artifact Lineage"))
    else:
        click.echo(format_lineage_tree(tree))


def _render_node_list_rich(records) -> None:
    """Render node selection table with Rich."""
    from binex.cli.ui import get_console, make_table, status_text

    table = make_table(
        ("#", {"style": "dim", "width": 4, "justify": "right"}),
        ("Node", {"style": "bold", "min_width": 14}),
        ("Status", {"min_width": 10}),
        ("Agent", {"style": "dim"}),
        ("Latency", {"justify": "right"}),
        title="Select Node",
    )
    for i, rec in enumerate(records, 1):
        table.add_row(
            str(i), rec.task_id, status_text(rec.status.value),
            rec.agent_id, f"{rec.latency_ms}ms" if rec.latency_ms else "-",
        )
    get_console().print(table)


def _render_node_list_plain(records) -> None:
    """Render node selection list in plain text."""
    for i, rec in enumerate(records, 1):
        latency = f"{rec.latency_ms}ms" if rec.latency_ms else ""
        click.echo(
            f"  {i:>3})  {rec.task_id:<20} {rec.status.value:<12} {latency}"
        )


def _render_node_rich(rec, node_arts, node_total_cost: float) -> None:
    """Render node detail as a Rich panel."""
    from rich.console import Group
    from rich.text import Text

    from binex.cli.ui import STATUS_CONFIG, get_console, make_panel, make_table

    console = get_console()

    _, style = STATUS_CONFIG.get(rec.status.value, (rec.status.value, "dim"))

    # Info lines
    info = Text()
    info.append("Agent: ", style="dim")
    info.append(rec.agent_id, style="bold")
    info.append("  ·  Status: ", style="dim")
    info.append(rec.status.value, style=style)
    latency = f"{rec.latency_ms}ms" if rec.latency_ms else "-"
    info.append(f"  ·  Latency: {latency}", style="dim")
    if node_total_cost > 0:
        info.append(f"  ·  Cost: ${node_total_cost:.4f}", style="cyan")

    parts = [info]

    if rec.model:
        model_line = Text()
        model_line.append("Model: ", style="dim")
        model_line.append(rec.model)
        parts.append(model_line)

    if rec.error:
        err_line = Text()
        err_line.append("Error: ", style="red bold")
        err_line.append(rec.error, style="red")
        parts.append(err_line)

    # Artifacts table
    if node_arts:
        parts.append(Text())
        art_table = make_table(
            ("ID", {"style": "dim", "min_width": 16}),
            ("Type", {"style": "yellow", "min_width": 10}),
            ("Preview", {"min_width": 30}),
            title=f"Artifacts ({len(node_arts)})",
        )
        for art in node_arts:
            art_table.add_row(
                art.id[:16], art.type, _preview(art.content, max_len=60),
            )
        parts.append(art_table)

    panel = make_panel(
        Group(*parts),
        title=f"[bold]{rec.task_id}[/bold]",
        subtitle=f"run: {rec.run_id}" if hasattr(rec, "run_id") else None,
    )
    console.print(panel)


def _render_node_plain(rec, node_arts, node_total_cost: float) -> None:
    """Render node detail in plain text."""
    click.echo(f"  Node: {rec.task_id}")
    click.echo(f"  Agent: {rec.agent_id}")
    click.echo(f"  Status: {rec.status.value}")
    click.echo(f"  Latency: {rec.latency_ms}ms" if rec.latency_ms else "  Latency: -")
    if rec.model:
        click.echo(f"  Model: {rec.model}")
    if rec.error:
        click.echo(f"  Error: {rec.error}")
    if node_arts:
        click.echo(f"  Artifacts: {len(node_arts)}")
        for art in node_arts:
            click.echo(f"    - {art.id} ({art.type}): {_preview(art.content)}")
    if node_total_cost > 0:
        click.echo(f"  Cost: ${node_total_cost:.4f}")


def _render_diagnose_rich(report) -> None:
    """Render diagnostic report with Rich formatting."""
    from rich.table import Table

    from binex.cli.ui import get_console, make_panel

    console = get_console()

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
                a.node_id, f"{a.latency_ms:.0f}ms",
                f"{a.median_ms:.0f}ms", f"{a.ratio:.1f}x",
            )
        console.print(table)

    if report.recommendations:
        rec_text = "\n".join(f"\u2022 {r}" for r in report.recommendations)
        console.print(make_panel(rec_text, title="Recommendations"))


def _render_diagnose_plain(report) -> None:
    """Render diagnostic report in plain text."""
    click.echo(f"  Run: {report.run_id}")
    click.echo(f"  Status: {report.status}")
    if report.root_cause:
        click.echo(f"  Root Cause: {report.root_cause.node_id}")
        click.echo(f"    Error: {report.root_cause.error_message}")
        click.echo(f"    Pattern: {report.root_cause.pattern}")
    if report.affected_nodes:
        click.echo(f"  Affected: {', '.join(report.affected_nodes)}")
    if report.latency_anomalies:
        click.echo("  Latency Anomalies:")
        for a in report.latency_anomalies:
            click.echo(f"    {a.node_id}: {a.latency_ms:.0f}ms ({a.ratio:.1f}x median)")
    if report.recommendations:
        click.echo("  Recommendations:")
        for r in report.recommendations:
            click.echo(f"    - {r}")
