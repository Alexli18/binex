"""Tests for execution store backends (InMemory + SQLite)."""

from __future__ import annotations

import tempfile

import pytest

from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryExecutionStore


@pytest.fixture
def exec_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


def _make_run(run_id: str = "run_01", status: str = "running") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-workflow",
        status=status,
        total_nodes=3,
    )


def _make_record(id: str, run_id: str = "run_01", task_id: str = "node1") -> ExecutionRecord:
    return ExecutionRecord(
        id=id,
        run_id=run_id,
        task_id=task_id,
        agent_id="local://echo",
        status=TaskStatus.COMPLETED,
        latency_ms=100,
        trace_id="trace_01",
    )


class TestInMemoryExecutionStore:
    @pytest.mark.asyncio
    async def test_create_and_get_run(self, exec_store: InMemoryExecutionStore) -> None:
        run = _make_run()
        await exec_store.create_run(run)
        result = await exec_store.get_run("run_01")
        assert result is not None
        assert result.run_id == "run_01"

    @pytest.mark.asyncio
    async def test_get_missing_run(self, exec_store: InMemoryExecutionStore) -> None:
        result = await exec_store.get_run("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_run(self, exec_store: InMemoryExecutionStore) -> None:
        await exec_store.create_run(_make_run())
        updated = _make_run(status="completed")
        updated.completed_nodes = 3
        await exec_store.update_run(updated)
        result = await exec_store.get_run("run_01")
        assert result is not None
        assert result.status == "completed"
        assert result.completed_nodes == 3

    @pytest.mark.asyncio
    async def test_list_runs(self, exec_store: InMemoryExecutionStore) -> None:
        await exec_store.create_run(_make_run("r1"))
        await exec_store.create_run(_make_run("r2"))
        runs = await exec_store.list_runs()
        assert len(runs) == 2

    @pytest.mark.asyncio
    async def test_record_and_get_step(self, exec_store: InMemoryExecutionStore) -> None:
        rec = _make_record("rec_01", task_id="planner")
        await exec_store.record(rec)
        result = await exec_store.get_step("run_01", "planner")
        assert result is not None
        assert result.id == "rec_01"

    @pytest.mark.asyncio
    async def test_get_missing_step(self, exec_store: InMemoryExecutionStore) -> None:
        result = await exec_store.get_step("run_01", "missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_records(self, exec_store: InMemoryExecutionStore) -> None:
        await exec_store.record(_make_record("r1", task_id="n1"))
        await exec_store.record(_make_record("r2", task_id="n2"))
        await exec_store.record(_make_record("r3", run_id="run_02", task_id="n1"))
        records = await exec_store.list_records("run_01")
        assert len(records) == 2


class TestSqliteExecutionStore:
    @pytest.mark.asyncio
    async def test_create_and_get_run(self) -> None:
        from binex.stores.backends.sqlite import SqliteExecutionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            await store.initialize()
            try:
                run = _make_run()
                await store.create_run(run)
                result = await store.get_run("run_01")
                assert result is not None
                assert result.run_id == "run_01"
                assert result.workflow_name == "test-workflow"
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_record_and_get_step(self) -> None:
        from binex.stores.backends.sqlite import SqliteExecutionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            await store.initialize()
            try:
                rec = _make_record("rec_01", task_id="planner")
                await store.record(rec)
                result = await store.get_step("run_01", "planner")
                assert result is not None
                assert result.id == "rec_01"
                assert result.status == TaskStatus.COMPLETED
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_update_run(self) -> None:
        from binex.stores.backends.sqlite import SqliteExecutionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            await store.initialize()
            try:
                await store.create_run(_make_run())
                updated = _make_run(status="completed")
                updated.completed_nodes = 3
                await store.update_run(updated)
                result = await store.get_run("run_01")
                assert result is not None
                assert result.status == "completed"
                assert result.completed_nodes == 3
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_list_runs(self) -> None:
        from binex.stores.backends.sqlite import SqliteExecutionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            await store.initialize()
            try:
                await store.create_run(_make_run("r1"))
                await store.create_run(_make_run("r2"))
                runs = await store.list_runs()
                assert len(runs) == 2
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_list_records(self) -> None:
        from binex.stores.backends.sqlite import SqliteExecutionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            await store.initialize()
            try:
                await store.record(_make_record("r1", task_id="n1"))
                await store.record(_make_record("r2", task_id="n2"))
                await store.record(_make_record("r3", run_id="run_02", task_id="n1"))
                records = await store.list_records("run_01")
                assert len(records) == 2
            finally:
                await store.close()
