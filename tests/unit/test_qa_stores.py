"""QA tests for store backends — P0 test cases from the QA plan.

TC-STO-001: SqliteExecutionStore: create_run with duplicate run_id
TC-STO-002: SqliteExecutionStore: list_records for non-existent run_id
TC-STO-003: FilesystemArtifactStore: get() with corrupted JSON file
TC-STO-005: SqliteExecutionStore: close() prevents aiosqlite hang
TC-SEC-003: Path traversal — artifact_id with ``../`` in filesystem store
TC-SEC-004: SQL injection — run_id with SQL injection payload in sqlite store
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.sqlite import SqliteExecutionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(run_id: str = "run_01", status: str = "running") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-workflow",
        status=status,
        total_nodes=3,
    )


def _make_record(
    id: str, run_id: str = "run_01", task_id: str = "node1",
) -> ExecutionRecord:
    return ExecutionRecord(
        id=id,
        run_id=run_id,
        task_id=task_id,
        agent_id="local://echo",
        status=TaskStatus.COMPLETED,
        latency_ms=100,
        trace_id="trace_01",
    )


def _make_artifact(
    id: str,
    run_id: str = "run_01",
    produced_by: str = "node1",
    derived_from: list[str] | None = None,
) -> Artifact:
    return Artifact(
        id=id,
        run_id=run_id,
        type="test",
        content={"data": id},
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


# ---------------------------------------------------------------------------
# TC-STO-001: create_run with duplicate run_id
# ---------------------------------------------------------------------------

class TestSqliteDuplicateRun:
    """TC-STO-001: inserting a run with an already-existing run_id should
    raise an IntegrityError (PRIMARY KEY constraint)."""

    @pytest.mark.asyncio
    async def test_create_run_duplicate_raises(self, tmp_path: str) -> None:
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        try:
            await store.create_run(_make_run("dup_run"))

            # Act & Assert — second insert with same PK must fail
            with pytest.raises(Exception):
                await store.create_run(_make_run("dup_run"))
        finally:
            await store.close()


# ---------------------------------------------------------------------------
# TC-STO-002: list_records for non-existent run_id
# ---------------------------------------------------------------------------

class TestSqliteListRecordsEmpty:
    """TC-STO-002: list_records for a run_id that has no records should
    return an empty list, not raise."""

    @pytest.mark.asyncio
    async def test_list_records_nonexistent_run(self, tmp_path: str) -> None:
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        try:
            # Act
            records = await store.list_records("nonexistent_run")

            # Assert
            assert records == []
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_list_records_empty_after_other_run(self, tmp_path: str) -> None:
        """Records exist for run_01 but query is for run_02."""
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        try:
            await store.record(_make_record("rec_01", run_id="run_01"))

            # Act
            records = await store.list_records("run_02")

            # Assert
            assert records == []
        finally:
            await store.close()


# ---------------------------------------------------------------------------
# TC-STO-003: FilesystemArtifactStore: get() with corrupted JSON
# ---------------------------------------------------------------------------

class TestFilesystemCorruptedJson:
    """TC-STO-003: a corrupted JSON file on disk should raise (not silently
    return None), because callers must know the artifact exists but is broken."""

    @pytest.mark.asyncio
    async def test_get_corrupted_json_via_rglob_raises(self, tmp_path: str) -> None:
        """Corrupted file found via rglob scan (index is empty)."""
        # Arrange
        run_dir = os.path.join(str(tmp_path), "run_01")
        os.makedirs(run_dir, exist_ok=True)
        corrupt_path = os.path.join(run_dir, "bad_art.json")
        with open(corrupt_path, "w") as f:
            f.write("{this is not valid json!!!")

        store = FilesystemArtifactStore(base_path=str(tmp_path))

        # Act & Assert — json.loads raises on corrupted content
        with pytest.raises((json.JSONDecodeError, Exception)):
            await store.get("bad_art")

    @pytest.mark.asyncio
    async def test_get_corrupted_json_via_index_raises(self, tmp_path: str) -> None:
        """Store an artifact, then corrupt the file on disk."""
        # Arrange
        store = FilesystemArtifactStore(base_path=str(tmp_path))
        art = _make_artifact("good_art")
        await store.store(art)

        # Corrupt the file after storing
        corrupt_path = os.path.join(str(tmp_path), "run_01", "good_art.json")
        with open(corrupt_path, "w") as f:
            f.write("NOT JSON")

        # Act & Assert — reading via index hits the corrupted file
        with pytest.raises((json.JSONDecodeError, Exception)):
            await store.get("good_art")


# ---------------------------------------------------------------------------
# TC-STO-005: close() prevents aiosqlite hang
# ---------------------------------------------------------------------------

class TestSqliteClose:
    """TC-STO-005: calling close() should clean up internal state so the
    connection is released."""

    @pytest.mark.asyncio
    async def test_close_resets_state(self, tmp_path: str) -> None:
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        assert store._db is not None
        assert store._initialized is True

        # Act
        await store.close()

        # Assert — internal state is cleaned up
        assert store._db is None
        assert store._initialized is False

    @pytest.mark.asyncio
    async def test_close_idempotent(self, tmp_path: str) -> None:
        """Calling close() twice should not raise."""
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()

        # Act — double close
        await store.close()
        await store.close()

        # Assert — still cleaned up, no exception
        assert store._db is None
        assert store._initialized is False

    @pytest.mark.asyncio
    async def test_reinitialize_after_close(self, tmp_path: str) -> None:
        """Store should be usable again after close + re-initialize."""
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        await store.create_run(_make_run("r1"))
        await store.close()

        # Act — re-open and query
        await store.initialize()
        try:
            result = await store.get_run("r1")

            # Assert — data persisted across close/reopen
            assert result is not None
            assert result.run_id == "r1"
        finally:
            await store.close()


# ---------------------------------------------------------------------------
# TC-SEC-003: Path traversal in FilesystemArtifactStore
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """TC-SEC-003: artifact_id containing ``../`` must not allow reading or
    writing files outside the store's base directory."""

    @pytest.mark.asyncio
    async def test_store_traversal_stays_within_base(self, tmp_path: str) -> None:
        """Storing an artifact with ``../`` in the id must raise ValueError."""
        # Arrange
        base_path = os.path.join(str(tmp_path), "artifacts")
        os.makedirs(base_path, exist_ok=True)
        store = FilesystemArtifactStore(base_path=base_path)

        traversal_id = "../../etc/pwned"
        art = _make_artifact(traversal_id, run_id="run_01")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid path component"):
            await store.store(art)

    @pytest.mark.asyncio
    async def test_get_traversal_artifact_id(self, tmp_path: str) -> None:
        """Calling get() with a ``../`` artifact_id must raise ValueError."""
        # Arrange
        base_path = os.path.join(str(tmp_path), "artifacts")
        os.makedirs(base_path, exist_ok=True)
        store = FilesystemArtifactStore(base_path=base_path)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid path component"):
            await store.get("../secret")


# ---------------------------------------------------------------------------
# TC-SEC-004: SQL injection in SqliteExecutionStore
# ---------------------------------------------------------------------------

class TestSqlInjection:
    """TC-SEC-004: run_id containing SQL injection payloads must be handled
    safely by parameterized queries — no data corruption or extra results."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_run_id(self, tmp_path: str) -> None:
        """A run_id with SQL injection payload should be treated as a
        literal string, not executed as SQL."""
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        try:
            # Create a legitimate run
            await store.create_run(_make_run("legit_run"))

            # Act — query with SQL injection payload
            injection_payload = "'; DROP TABLE runs; --"
            result = await store.get_run(injection_payload)

            # Assert — no run found (payload is treated as literal string)
            assert result is None

            # The legitimate run must still be intact
            legit = await store.get_run("legit_run")
            assert legit is not None
            assert legit.run_id == "legit_run"
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_sql_injection_in_list_records(self, tmp_path: str) -> None:
        """SQL injection in list_records run_id parameter."""
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        try:
            await store.record(_make_record("r1", run_id="safe_run"))

            # Act — injection attempt via list_records
            injection_payload = "safe_run' OR '1'='1"
            records = await store.list_records(injection_payload)

            # Assert — should return empty, not all records
            assert records == []

            # Original data intact
            safe_records = await store.list_records("safe_run")
            assert len(safe_records) == 1
        finally:
            await store.close()

    @pytest.mark.asyncio
    async def test_sql_injection_in_create_run(self, tmp_path: str) -> None:
        """SQL injection payload as a run_id value in create_run."""
        # Arrange
        store = SqliteExecutionStore(db_path=f"{tmp_path}/test.db")
        await store.initialize()
        try:
            injection_id = "x'); DROP TABLE runs; --"
            run = _make_run(run_id=injection_id)

            # Act — should insert the payload as a literal string
            await store.create_run(run)

            # Assert — retrievable by the exact (injected) string
            result = await store.get_run(injection_id)
            assert result is not None
            assert result.run_id == injection_id

            # Table still exists and works
            all_runs = await store.list_runs()
            assert len(all_runs) == 1
        finally:
            await store.close()
