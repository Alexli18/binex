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


def _status_marker(status: str) -> str:
    if status == "completed":
        return "completed"
    if status == "failed":
        return "FAILED"
    return status


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
    runs = runs[:20]  # Show last 20

    click.echo()
    click.echo("  Recent runs:")
    click.echo()
    for i, run in enumerate(runs, 1):
        status = _status_marker(run.status)
        ago = _time_ago(run.started_at)
        click.echo(
            f"  {i:>3})  {_short_id(run.run_id):<18} "
            f"{run.workflow_name:<25} {status:<12} {ago}"
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

    try:
        from rich.console import Console
        from rich.markdown import Markdown
        from rich.panel import Panel

        console = Console()
        console.print(Panel(
            Markdown(content_str),
            title=f"{node} / {artifact.type}",
            subtitle=f"id: {artifact.id}",
            border_style="blue",
        ))
    except ImportError:
        click.echo(f"  ── {node} / {artifact.type} ──")
        click.echo(f"  {content_str}")
        click.echo(f"  id: {artifact.id}")
        click.echo()

    while True:
        choice = click.prompt(
            "  [l] lineage  [b] back  [q] quit",
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
                click.echo(format_lineage_tree(tree))
            else:
                click.echo("  No lineage data available.")
            continue
        click.echo("  Enter l, b, or q.")
