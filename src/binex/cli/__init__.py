"""Binex CLI — command-line interface."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

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
