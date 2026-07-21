"""CLI `binex clean` — reclaim space from the local store (node cache, ...)."""

from __future__ import annotations

import asyncio
from typing import Any

import click

from binex.cli import get_stores


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.group("clean", epilog="""\b
Examples:
  binex clean cache                    Clear all cached node results
  binex clean cache --older-than 7     Clear cache entries older than 7 days
  binex clean cache --dry-run          Show how much cache is stored
  binex clean workspaces               Delete all run workspaces
  binex clean workspaces --older-than 7 --dry-run
  binex clean blobs                    GC binary-artifact blobs not referenced by any run
""")
def clean_group() -> None:
    """Reclaim local disk space."""


@clean_group.command("cache")
@click.option("--older-than", type=float, default=None,
              help="Only clear entries older than this many days")
@click.option("--dry-run", is_flag=True, help="Report without deleting")
def clean_cache_cmd(older_than: float | None, dry_run: bool) -> None:
    """Clear cached node results."""
    asyncio.run(_clean_cache(older_than, dry_run))


async def _clean_cache(older_than: float | None, dry_run: bool) -> None:
    execution_store, _ = _get_stores()
    try:
        if dry_run:
            total = await execution_store.count_cache_entries()
            scope = (
                f" older than {older_than} days" if older_than is not None else ""
            )
            click.echo(f"{total} cache entries stored; would clear entries{scope}.")
            return
        deleted = await execution_store.clear_cache_entries(older_than_days=older_than)
        scope = f" older than {older_than} days" if older_than is not None else ""
        click.echo(f"Cleared {deleted} cache {'entry' if deleted == 1 else 'entries'}{scope}.")
    finally:
        await execution_store.close()


@clean_group.command("workspaces")
@click.option("--older-than", type=float, default=None,
              help="Only delete workspaces older than this many days")
@click.option("--dry-run", is_flag=True, help="Report without deleting")
def clean_workspaces_cmd(older_than: float | None, dry_run: bool) -> None:
    """Delete run workspaces (heavy git-backed dirs under .binex/workspaces)."""
    import shutil
    import time
    from pathlib import Path

    from binex.runtime.workspace import DEFAULT_BASE_DIR

    base = Path(DEFAULT_BASE_DIR)
    if not base.is_dir():
        click.echo("No workspaces to clean.")
        return

    cutoff = None if older_than is None else time.time() - older_than * 86400
    targets = [
        d for d in base.iterdir()
        if d.is_dir() and (cutoff is None or d.stat().st_mtime < cutoff)
    ]
    scope = f" older than {older_than} days" if older_than is not None else ""
    if dry_run:
        click.echo(f"{len(targets)} workspace(s){scope} would be deleted.")
        return
    for d in targets:
        shutil.rmtree(d, ignore_errors=True)
    click.echo(
        f"Deleted {len(targets)} workspace"
        f"{'' if len(targets) == 1 else 's'}{scope}."
    )


@clean_group.command("blobs")
@click.option("--dry-run", is_flag=True, help="Report without deleting")
def clean_blobs_cmd(dry_run: bool) -> None:
    """Garbage-collect binary-artifact blobs not referenced by any run (#76)."""
    asyncio.run(_clean_blobs(dry_run))


async def _clean_blobs(dry_run: bool) -> None:
    from binex.artifacts.binary import blob_dir, is_binary_artifact

    directory = blob_dir()
    if not directory.is_dir():
        click.echo("No blobs to clean.")
        return

    exec_store, art_store = _get_stores()
    referenced: set[str] = set()
    try:
        for run in await exec_store.list_runs():
            for art in await art_store.list_by_run(run.run_id):
                if is_binary_artifact(art):
                    sha = art.content.get("sha256")
                    if sha:
                        referenced.add(sha)
    finally:
        await exec_store.close()

    orphans = [p for p in directory.iterdir() if p.is_file() and p.name not in referenced]
    freed = sum(p.stat().st_size for p in orphans)
    if dry_run:
        click.echo(
            f"{len(orphans)} orphan blob(s) ({freed} bytes) would be deleted "
            f"({len(referenced)} still referenced)."
        )
        return
    for p in orphans:
        p.unlink(missing_ok=True)
    click.echo(
        f"Deleted {len(orphans)} orphan blob"
        f"{'' if len(orphans) == 1 else 's'} ({freed} bytes freed)."
    )
