"""Tests for SQLite lazy migration of iteration_number column.

Verifies that SqliteExecutionStore correctly migrates existing databases
that lack the iteration_number column in execution_records table.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import aiosqlite
import pytest

from binex.models.execution import ExecutionRecord
from binex.models.task import TaskStatus
from binex.stores.backends.sqlite import SqliteExecutionStore

# ---------------------------------------------------------------------------
# Helper: create a "legacy" database WITHOUT iteration_number column
# ---------------------------------------------------------------------------

OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    workflow_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    total_nodes INTEGER NOT NULL,
    completed_nodes INTEGER DEFAULT 0,
    failed_nodes INTEGER DEFAULT 0,
    forked_from TEXT,
    forked_at_step TEXT,
    total_cost REAL DEFAULT 0.0,
    workflow_path TEXT,
    workflow_hash TEXT
);
CREATE TABLE IF NOT EXISTS execution_records (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    parent_task_id TEXT,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    input_artifact_refs TEXT DEFAULT '[]',
    output_artifact_refs TEXT DEFAULT '[]',
    prompt TEXT,
    model TEXT,
    tool_calls TEXT,
    latency_ms INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS cost_records (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0.0,
    currency TEXT NOT NULL DEFAULT 'USD',
    source TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    model TEXT,
    timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_snapshots (
    hash TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


async def _create_legacy_db(db_path: str) -> None:
    """Create a database with the old schema (no iteration_number)."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    db = await aiosqlite.connect(db_path)
    await db.executescript(OLD_SCHEMA)
    await db.commit()
    await db.close()


async def _insert_legacy_record(db_path: str, record_id: str, run_id: str, task_id: str) -> None:
    """Insert a record into legacy DB (15 columns, no iteration_number)."""
    db = await aiosqlite.connect(db_path)
    now = datetime.now(UTC).isoformat()
    await db.execute(
        """INSERT INTO execution_records
           (id, run_id, task_id, parent_task_id, agent_id, status,
            input_artifact_refs, output_artifact_refs, prompt, model,
            tool_calls, latency_ms, timestamp, trace_id, error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (record_id, run_id, task_id, None, "llm://gpt-4o", "completed",
         "[]", "[]", "test prompt", "gpt-4o", None, 100, now, "trace-1", None),
    )
    await db.commit()
    await db.close()


async def _column_exists(db_path: str, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    db = await aiosqlite.connect(db_path)
    cursor = await db.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in await cursor.fetchall()]
    await db.close()
    return column in columns


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestIterationNumberMigration:
    """Verify lazy migration adds iteration_number to old databases."""

    async def test_legacy_db_lacks_column(self, tmp_path):
        """Precondition: legacy DB does NOT have iteration_number."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)
        assert not await _column_exists(db_path, "execution_records", "iteration_number")

    async def test_migration_adds_column(self, tmp_path):
        """Opening a legacy DB with SqliteExecutionStore adds iteration_number."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)

        store = SqliteExecutionStore(db_path)
        await store.initialize()
        await store.close()

        assert await _column_exists(db_path, "execution_records", "iteration_number")

    async def test_migration_idempotent(self, tmp_path):
        """Running initialize() twice does not fail (ALTER already applied)."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)

        store = SqliteExecutionStore(db_path)
        await store.initialize()
        await store.close()

        # Second init on same DB — migration should be silently skipped
        store2 = SqliteExecutionStore(db_path)
        await store2.initialize()
        await store2.close()

        assert await _column_exists(db_path, "execution_records", "iteration_number")

    async def test_read_legacy_record_after_migration(self, tmp_path):
        """Legacy records (without iteration_number) read as iteration_number=None."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)
        await _insert_legacy_record(db_path, "rec-1", "run-1", "node-a")

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        record = await store.get_step("run-1", "node-a")
        assert record is not None
        assert record.iteration_number is None
        assert record.task_id == "node-a"
        assert record.status == TaskStatus.COMPLETED

        await store.close()

    async def test_write_record_with_iteration_number_after_migration(self, tmp_path):
        """After migration, new records with iteration_number persist correctly."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        rec = ExecutionRecord(
            id="rec-loop-1", run_id="run-2", task_id="loop1.writer",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=200, trace_id="trace-2",
            iteration_number=3,
        )
        await store.record(rec)

        fetched = await store.get_step("run-2", "loop1.writer")
        assert fetched is not None
        assert fetched.iteration_number == 3

        await store.close()

    async def test_write_record_without_iteration_number_after_migration(self, tmp_path):
        """After migration, records without iteration_number still work (NULL)."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        rec = ExecutionRecord(
            id="rec-2", run_id="run-3", task_id="node-b",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=150, trace_id="trace-3",
        )
        await store.record(rec)

        fetched = await store.get_step("run-3", "node-b")
        assert fetched is not None
        assert fetched.iteration_number is None

        await store.close()

    async def test_mixed_records_legacy_and_new(self, tmp_path):
        """Legacy records + new records with iteration_number coexist."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)
        await _insert_legacy_record(db_path, "old-1", "run-mix", "node-old")

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        # Write new record with iteration_number
        rec = ExecutionRecord(
            id="new-1", run_id="run-mix", task_id="loop1.step",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=100, trace_id="trace-mix",
            iteration_number=1,
        )
        await store.record(rec)

        records = await store.list_records("run-mix")
        assert len(records) == 2

        old_rec = next(r for r in records if r.id == "old-1")
        new_rec = next(r for r in records if r.id == "new-1")

        assert old_rec.iteration_number is None
        assert new_rec.iteration_number == 1

        await store.close()

    async def test_list_records_on_legacy_db(self, tmp_path):
        """list_records works on legacy DB with multiple old records."""
        db_path = str(tmp_path / "binex.db")
        await _create_legacy_db(db_path)
        await _insert_legacy_record(db_path, "r1", "run-list", "n1")
        await _insert_legacy_record(db_path, "r2", "run-list", "n2")
        await _insert_legacy_record(db_path, "r3", "run-list", "n3")

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        records = await store.list_records("run-list")
        assert len(records) == 3
        assert all(r.iteration_number is None for r in records)

        await store.close()

    async def test_fresh_db_has_iteration_number(self, tmp_path):
        """A brand new DB (no legacy) also gets iteration_number via migration."""
        db_path = str(tmp_path / "fresh.db")

        store = SqliteExecutionStore(db_path)
        await store.initialize()
        await store.close()

        # The CREATE TABLE doesn't include iteration_number, but migration adds it
        assert await _column_exists(db_path, "execution_records", "iteration_number")

    async def test_iteration_number_zero_value(self, tmp_path):
        """iteration_number=0 is stored correctly (not confused with NULL)."""
        db_path = str(tmp_path / "binex.db")

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        rec = ExecutionRecord(
            id="rec-zero", run_id="run-zero", task_id="loop1.first",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=50, trace_id="trace-zero",
            iteration_number=0,
        )
        await store.record(rec)

        fetched = await store.get_step("run-zero", "loop1.first")
        assert fetched is not None
        assert fetched.iteration_number == 0
        assert fetched.iteration_number is not None

        await store.close()

    async def test_high_iteration_number(self, tmp_path):
        """Large iteration numbers are handled correctly."""
        db_path = str(tmp_path / "binex.db")

        store = SqliteExecutionStore(db_path)
        await store.initialize()

        rec = ExecutionRecord(
            id="rec-big", run_id="run-big", task_id="loop1.node",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=50, trace_id="trace-big",
            iteration_number=9999,
        )
        await store.record(rec)

        fetched = await store.get_step("run-big", "loop1.node")
        assert fetched is not None
        assert fetched.iteration_number == 9999

        await store.close()
