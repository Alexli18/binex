"""CLI `binex explore` command — interactive run and artifact browser."""

from __future__ import annotations

import asyncio
import json

import click

from binex.cli import get_stores, has_rich
from binex.trace.lineage import build_lineage_tree, format_lineage_tree


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _short_id(run_id: str) -> str:
    """Shorten run ID for display."""
    return run_id[:16] if len(run_id) > 16 else run_id


def _time_ago(dt) -> str:
    """Human-readable relative time."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _preview(content, max_len: int = 50) -> str:
    """Truncate content for preview."""
    if content is None:
        return "(empty)"
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    text = text.replace("\n", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _status_style(status: str) -> tuple[str, str]:
    """Return (display_text, rich_style) for a status."""
    from binex.cli.ui import STATUS_CONFIG
    return STATUS_CONFIG.get(status, (status, "dim"))


@click.command("explore", epilog="""\b
Examples:
  binex explore              Browse recent runs
  binex explore <run_id>     Jump to artifacts for a specific run
""")
@click.argument("run_id", required=False, default=None)
def explore_cmd(run_id: str | None) -> None:
    """Interactive browser for runs and artifacts."""
    asyncio.run(_explore(run_id))


async def _explore(run_id: str | None) -> None:
    exec_store, art_store = _get_stores()
    try:
        if run_id:
            await _browse_artifacts(exec_store, art_store, run_id)
        else:
            await _browse_runs(exec_store, art_store)
    finally:
        await exec_store.close()


async def _browse_runs(exec_store, art_store) -> None:
    """Level 1: list recent runs and let user pick one."""
    runs = await exec_store.list_runs()
    if not runs:
        click.echo("No runs found. Run a workflow first:")
        click.echo("  binex run examples/simple.yaml --var input=\"hello\"")
        return

    runs.sort(key=lambda r: r.started_at, reverse=True)
    runs = runs[:20]

    click.echo()

    if has_rich():
        from binex.cli.ui import get_console, make_table, status_text

        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Run ID", {"style": "cyan", "min_width": 16}),
            ("Workflow", {"min_width": 20}),
            ("Status", {"min_width": 10}),
            ("Nodes", {"justify": "center", "min_width": 6}),
            ("When", {"style": "dim", "min_width": 8}),
            title="Recent Runs",
        )

        for i, run in enumerate(runs, 1):
            nodes = f"{run.completed_nodes}/{run.total_nodes}"
            table.add_row(
                str(i),
                _short_id(run.run_id),
                run.workflow_name,
                status_text(run.status),
                nodes,
                _time_ago(run.started_at),
            )
        get_console().print(table)
    else:
        click.echo("  Recent runs:")
        click.echo()
        for i, run in enumerate(runs, 1):
            status_text, _ = _status_style(run.status)
            ago = _time_ago(run.started_at)
            click.echo(
                f"  {i:>3})  {_short_id(run.run_id):<18} "
                f"{run.workflow_name:<25} {status_text:<12} {ago}"
            )

    click.echo()

    while True:
        choice = click.prompt(
            "  Select run (or q to quit)", default="1",
        )
        if choice.lower() == "q":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(runs):
                await _browse_artifacts(exec_store, art_store, runs[idx].run_id)
                return
        except ValueError:
            pass
        click.echo(f"  Invalid choice. Enter 1-{len(runs)} or q.")


async def _browse_artifacts(exec_store, art_store, run_id: str) -> None:
    """Level 2: list artifacts for a run and let user pick one."""
    artifacts = await art_store.list_by_run(run_id)
    if not artifacts:
        click.echo(f"  No artifacts found for run '{_short_id(run_id)}'.")
        return

    while True:
        click.echo()
        _print_artifacts_table(artifacts, run_id)
        click.echo()

        choice = click.prompt(
            "  Select artifact (or b=back, q=quit)", default="1",
        )
        if choice.lower() == "q":
            return
        if choice.lower() == "b":
            await _browse_runs(exec_store, art_store)
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(artifacts):
                await _show_artifact(exec_store, art_store, artifacts[idx])
                continue
        except ValueError:
            pass
        click.echo(f"  Invalid choice. Enter 1-{len(artifacts)}, b, or q.")


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


async def _show_artifact(exec_store, art_store, artifact) -> None:
    """Level 3: show artifact detail with actions."""
    content_str = artifact.content if artifact.content is not None else ""
    if not isinstance(content_str, str):
        content_str = json.dumps(content_str, default=str, indent=2)

    node = artifact.lineage.produced_by if artifact.lineage else "?"
    click.echo()
    _print_artifact_detail(artifact, node, content_str)

    while True:
        _print_action_hints()
        choice = click.prompt(
            "  Action" if has_rich() else "  [l] lineage  [b] back  [q] quit",
            default="b",
        )
        if choice.lower() == "b":
            return
        if choice.lower() == "q":
            raise SystemExit(0)
        if choice.lower() == "l":
            await _show_lineage(art_store, artifact.id)
            continue
        click.echo("  Enter l, b, or q.")


def _print_artifact_detail(artifact, node: str, content_str: str) -> None:
    """Render artifact detail view (rich or plain)."""
    if has_rich():
        from rich.markdown import Markdown
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        console = get_console()
        meta = Text()
        meta.append("Node: ", style="dim")
        meta.append(node, style="magenta bold")
        meta.append("  Type: ", style="dim")
        meta.append(artifact.type, style="yellow")
        meta.append("  Status: ", style="dim")
        _, style = _status_style(artifact.status)
        meta.append(artifact.status, style=style)
        console.print(meta)
        console.print()
        console.print(make_panel(
            Markdown(content_str),
            title=f"{node} / {artifact.type}",
            subtitle=f"id: {artifact.id}",
        ))
    else:
        click.echo(f"  ── {node} / {artifact.type} ──")
        click.echo(f"  {content_str}")
        click.echo(f"  id: {artifact.id}")
        click.echo()


def _print_action_hints() -> None:
    """Print action menu hints."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console()
        hint = Text()
        hint.append("  [", style="dim")
        hint.append("l", style="cyan bold")
        hint.append("] lineage  [", style="dim")
        hint.append("b", style="cyan bold")
        hint.append("] back  [", style="dim")
        hint.append("q", style="cyan bold")
        hint.append("] quit", style="dim")
        console.print(hint)
