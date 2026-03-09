"""CLI `binex explore` command — interactive run and artifact browser."""

from __future__ import annotations

import asyncio
import json

import click

from binex.cli import get_stores
from binex.trace.lineage import build_lineage_tree, format_lineage_tree


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _has_rich() -> bool:
    try:
        import rich  # noqa: F401
        return True
    except ImportError:
        return False


def _short_id(run_id: str) -> str:
    """Shorten run ID for display."""
    return run_id[:16] if len(run_id) > 16 else run_id


def _time_ago(dt) -> str:
    """Human-readable relative time."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
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
    if status == "completed":
        return "completed", "green"
    if status == "failed":
        return "FAILED", "bold red"
    if status == "running":
        return "running", "yellow"
    return status, "dim"


@click.command("explore")
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

    if _has_rich():
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text

        console = Console()
        table = Table(
            title="Recent Runs",
            title_style="bold cyan",
            show_header=True,
            header_style="bold",
            border_style="dim",
            pad_edge=False,
            show_edge=True,
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Run ID", style="cyan", min_width=16)
        table.add_column("Workflow", min_width=20)
        table.add_column("Status", min_width=10)
        table.add_column("Nodes", justify="center", min_width=6)
        table.add_column("When", style="dim", min_width=8)

        for i, run in enumerate(runs, 1):
            status_text, status_style = _status_style(run.status)
            nodes = f"{run.completed_nodes}/{run.total_nodes}"
            table.add_row(
                str(i),
                _short_id(run.run_id),
                run.workflow_name,
                Text(status_text, style=status_style),
                nodes,
                _time_ago(run.started_at),
            )
        console.print(table)
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

        if _has_rich():
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(
                title=f"Artifacts — {_short_id(run_id)}",
                title_style="bold cyan",
                show_header=True,
                header_style="bold",
                border_style="dim",
                show_edge=True,
            )
            table.add_column("#", style="dim", width=4, justify="right")
            table.add_column("Node", style="magenta", min_width=16)
            table.add_column("Type", style="yellow", min_width=10)
            table.add_column("Preview", min_width=30)

            for i, art in enumerate(artifacts, 1):
                node = art.lineage.produced_by if art.lineage else "?"
                table.add_row(
                    str(i),
                    node,
                    art.type,
                    _preview(art.content, max_len=60),
                )
            console.print(table)
        else:
            click.echo(f"  Artifacts for {_short_id(run_id)}:")
            click.echo()
            for i, art in enumerate(artifacts, 1):
                node = art.lineage.produced_by if art.lineage else "?"
                preview = _preview(art.content)
                click.echo(
                    f"  {i:>3})  {node:<20} {art.type:<12} {preview}"
                )

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


async def _show_artifact(exec_store, art_store, artifact) -> None:
    """Level 3: show artifact detail with actions."""
    content_str = artifact.content if artifact.content is not None else ""
    if not isinstance(content_str, str):
        content_str = json.dumps(content_str, default=str, indent=2)

    node = artifact.lineage.produced_by if artifact.lineage else "?"
    click.echo()

    if _has_rich():
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        # Metadata line
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

        console.print(Panel(
            Markdown(content_str),
            title=f"{node} / {artifact.type}",
            subtitle=f"id: {artifact.id}",
            border_style="blue",
            padding=(1, 2),
        ))
    else:
        click.echo(f"  ── {node} / {artifact.type} ──")
        click.echo(f"  {content_str}")
        click.echo(f"  id: {artifact.id}")
        click.echo()

    while True:
        if _has_rich():
            from rich.console import Console
            from rich.text import Text

            console = Console()
            hint = Text()
            hint.append("  [", style="dim")
            hint.append("l", style="cyan bold")
            hint.append("] lineage  [", style="dim")
            hint.append("b", style="cyan bold")
            hint.append("] back  [", style="dim")
            hint.append("q", style="cyan bold")
            hint.append("] quit", style="dim")
            console.print(hint)

        choice = click.prompt(
            "  Action" if _has_rich() else "  [l] lineage  [b] back  [q] quit",
            default="b",
        )
        if choice.lower() == "b":
            return
        if choice.lower() == "q":
            raise SystemExit(0)
        if choice.lower() == "l":
            tree = await build_lineage_tree(art_store, artifact.id)
            if tree:
                click.echo()
                if _has_rich():
                    from rich.console import Console
                    from rich.panel import Panel

                    console = Console()
                    console.print(Panel(
                        format_lineage_tree(tree),
                        title="Lineage",
                        border_style="green",
                        padding=(1, 2),
                    ))
                else:
                    click.echo(format_lineage_tree(tree))
            else:
                click.echo("  No lineage data available.")
            continue
        click.echo("  Enter l, b, or q.")
