"""Binex CLI — command-line interface."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import click

from binex.settings import Settings
from binex.stores import create_artifact_store, create_execution_store
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.sqlite import SqliteExecutionStore


def get_stores() -> tuple[SqliteExecutionStore, FilesystemArtifactStore]:
    """Create persistent stores (sqlite + filesystem). Call from CLI commands."""
    settings = Settings()
    exec_store = create_execution_store(
        backend="sqlite", db_path=settings.db_path,
    )
    art_store = create_artifact_store(
        backend="filesystem", base_path=settings.artifacts_dir,
    )
    return exec_store, art_store


def run_async(coro_fn: Callable[..., Coroutine], *args: Any) -> Any:
    """Run an async function with persistent stores, closing sqlite on exit."""
    async def _wrapper():
        result = await coro_fn(*args)
        return result
    return asyncio.run(_wrapper())


def has_rich() -> bool:
    """Check if the rich library is available and color is not disabled."""
    ctx = click.get_current_context(silent=True)
    if ctx and ctx.color is False:
        return False
    try:
        import rich  # noqa: F401
        return True
    except ImportError:
        return False


def render_terminal_artifacts(
    artifacts: list,
    terminal_nodes: list[str],
    *,
    max_rich_len: int = 4000,
    max_plain_len: int = 2000,
) -> None:
    """Render terminal node artifacts with Rich panels (or plain fallback)."""
    terminal_arts = [
        a for a in artifacts if a.lineage.produced_by in terminal_nodes
    ]
    if not terminal_arts:
        return

    try:
        from rich.markdown import Markdown

        from binex.cli.ui import get_console, make_panel

        console = get_console()
        for art in terminal_arts:
            content = _prepare_content(art.content, max_rich_len)
            console.print(make_panel(
                Markdown(content),
                title=f"[bold]{art.lineage.produced_by}[/bold]",
                subtitle=art.type,
            ))
    except ImportError:
        click.echo(f"\n{'── Result ':─<60}")
        for art in terminal_arts:
            content = art.content
            if isinstance(content, str) and len(content) > max_plain_len:
                content = content[:max_plain_len] + "..."
            click.echo(f"[{art.lineage.produced_by}] {art.type}:")
            click.echo(f"  {content}")


def _prepare_content(content, max_len: int) -> str:
    """Convert content to string and truncate."""
    import json as _json

    if content is None:
        return ""
    if not isinstance(content, str):
        content = _json.dumps(content, default=str, indent=2)
    if len(content) > max_len:
        return content[:max_len] + "..."
    return content


# ---------------------------------------------------------------------------
# Grouped help formatter
# ---------------------------------------------------------------------------

COMMAND_SECTIONS: list[tuple[str, list[str]]] = [
    ("Core commands", ["run", "cancel", "replay"]),
    ("Inspect & debug", ["debug", "trace", "diff", "artifacts", "cost", "explore"]),
    ("Setup & scaffold", ["init", "start", "scaffold", "hello"]),
    ("System", ["dev", "doctor", "validate"]),
]


class BinexGroup(click.Group):
    """Custom group that displays commands in categorised sections."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        # Collect all registered commands
        commands: dict[str, click.Command] = {}
        for name in self.list_commands(ctx):
            cmd = self.get_command(ctx, name)
            if cmd is not None and not cmd.hidden:
                commands[name] = cmd

        if not commands:
            return

        listed: set[str] = set()

        for section_name, section_cmds in COMMAND_SECTIONS:
            rows: list[tuple[str, str]] = []
            for cmd_name in section_cmds:
                if cmd_name in commands:
                    cmd = commands[cmd_name]
                    help_text = cmd.get_short_help_str(limit=formatter.width)
                    rows.append((cmd_name, help_text))
                    listed.add(cmd_name)
            if rows:
                with formatter.section(section_name):
                    formatter.write_dl(rows)

        # Any unlisted commands go into "Other"
        other_rows = [
            (name, commands[name].get_short_help_str(limit=formatter.width))
            for name in sorted(commands)
            if name not in listed
        ]
        if other_rows:
            with formatter.section("Other commands"):
                formatter.write_dl(other_rows)
