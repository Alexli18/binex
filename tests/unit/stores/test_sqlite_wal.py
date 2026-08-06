"""WAL mode for the SQLite store — concurrent UI reads during orchestrator writes."""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from binex.models.execution import RunSummary
from binex.stores.backends.sqlite import SqliteExecutionStore


def _run(run_id: str) -> RunSummary:
    return RunSummary(
        run_id=run_id, workflow_name="wf", status="running", total_nodes=1,
    )


@pytest.mark.asyncio
async def test_wal_pragmas_applied():
    with tempfile.TemporaryDirectory() as d:
        store = SqliteExecutionStore(os.path.join(d, "binex.db"))
        db = await store._ensure_initialized()

        mode = await (await db.execute("PRAGMA journal_mode")).fetchone()
        timeout = await (await db.execute("PRAGMA busy_timeout")).fetchone()

        assert mode is not None and mode[0].lower() == "wal"
        assert timeout is not None and timeout[0] == 5000
        await store.close()


@pytest.mark.asyncio
async def test_concurrent_read_during_write_no_lock():
    """A second connection can read while the first writes — no 'database is locked'."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "binex.db")
        writer = SqliteExecutionStore(path)
        await writer.create_run(_run("seed"))  # initializes the file in WAL

        reader = SqliteExecutionStore(path)
        await reader._ensure_initialized()

        async def write_many() -> None:
            for i in range(30):
                await writer.create_run(_run(f"run_{i}"))
                await asyncio.sleep(0)

        async def read_many() -> None:
            for _ in range(30):
                await reader.list_runs()
                await asyncio.sleep(0)

        # Should complete without raising sqlite "database is locked".
        await asyncio.gather(write_many(), read_many())

        assert len(await reader.list_runs()) >= 30
        await writer.close()
        await reader.close()
