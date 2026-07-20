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
