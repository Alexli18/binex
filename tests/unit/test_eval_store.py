"""Tests for eval store methods — baselines + eval_results on both backends."""

from __future__ import annotations

import os
import tempfile

import pytest
import pytest_asyncio

from binex.models.execution import RunSummary
from binex.stores.backends.memory import InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(run_id: str, **kwargs) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test",
        status="completed",
        total_nodes=1,
        **kwargs,
    )


class _FakeEvalResult:
    """Minimal stand-in for EvalResult to avoid circular imports in this test."""

    def __init__(self, suite_name: str, suite_path: str | None = None):
        from datetime import UTC, datetime

        self.suite_name = suite_name
        self.suite_path = suite_path
        self.executed_at = datetime.now(UTC)
        self.total = 1
        self.passed = 1
        self.failed = 0
        self.no_baseline = 0

    def model_dump_json(self) -> str:
        import json

        return json.dumps(
            {
                "suite_name": self.suite_name,
                "suite_path": self.suite_path,
                "total": self.total,
                "passed": self.passed,
            }
        )


# ---------------------------------------------------------------------------
# InMemory backend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_set_get_baselines():
    store = InMemoryExecutionStore()
    await store.set_baseline("suite-a", "case-1", "run-001")
    await store.set_baseline("suite-a", "case-2", "run-002")

    baselines = await store.get_baselines("suite-a")
    assert baselines == {"case-1": "run-001", "case-2": "run-002"}


@pytest.mark.asyncio
async def test_memory_baseline_upsert():
    store = InMemoryExecutionStore()
    await store.set_baseline("suite-a", "case-1", "run-001")
    await store.set_baseline("suite-a", "case-1", "run-002")  # overwrite

    baselines = await store.get_baselines("suite-a")
    assert baselines["case-1"] == "run-002"


@pytest.mark.asyncio
async def test_memory_baselines_isolated_by_suite():
    store = InMemoryExecutionStore()
    await store.set_baseline("suite-a", "case-1", "run-001")
    await store.set_baseline("suite-b", "case-1", "run-999")

    assert await store.get_baselines("suite-a") == {"case-1": "run-001"}
    assert await store.get_baselines("suite-b") == {"case-1": "run-999"}
    assert await store.get_baselines("suite-c") == {}


@pytest.mark.asyncio
async def test_memory_save_list_get_eval_result():
    store = InMemoryExecutionStore()
    result = _FakeEvalResult("suite-a", "/path/to/suite.yaml")
    result_id = await store.save_eval_result(result)

    assert result_id.startswith("eval_")

    listing = await store.list_eval_results()
    assert len(listing) == 1
    assert listing[0]["suite_name"] == "suite-a"

    fetched = await store.get_eval_result(result_id)
    assert fetched is not None
    assert fetched["suite_name"] == "suite-a"


@pytest.mark.asyncio
async def test_memory_list_eval_results_filtered():
    store = InMemoryExecutionStore()
    await store.save_eval_result(_FakeEvalResult("suite-a"))
    await store.save_eval_result(_FakeEvalResult("suite-b"))

    a_results = await store.list_eval_results(suite_name="suite-a")
    assert len(a_results) == 1
    assert a_results[0]["suite_name"] == "suite-a"


@pytest.mark.asyncio
async def test_memory_get_eval_result_missing():
    store = InMemoryExecutionStore()
    assert await store.get_eval_result("eval_nonexistent") is None


@pytest.mark.asyncio
async def test_memory_run_new_fields_round_trip():
    store = InMemoryExecutionStore()
    run = _make_run("run-42", eval_suite_id="suite-a", eval_case_id="case-1", source="eval")
    await store.create_run(run)

    fetched = await store.get_run("run-42")
    assert fetched is not None
    assert fetched.eval_suite_id == "suite-a"
    assert fetched.eval_case_id == "case-1"
    assert fetched.source == "eval"


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sqlite_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = SqliteExecutionStore(db_path)
        await store.initialize()
        try:
            yield store
        finally:
            await store.close()


@pytest.mark.asyncio
async def test_sqlite_set_get_baselines(sqlite_store):
    await sqlite_store.set_baseline("suite-a", "case-1", "run-001")
    await sqlite_store.set_baseline("suite-a", "case-2", "run-002")

    baselines = await sqlite_store.get_baselines("suite-a")
    assert baselines == {"case-1": "run-001", "case-2": "run-002"}


@pytest.mark.asyncio
async def test_sqlite_baseline_upsert(sqlite_store):
    await sqlite_store.set_baseline("suite-a", "case-1", "run-001")
    await sqlite_store.set_baseline("suite-a", "case-1", "run-002")

    baselines = await sqlite_store.get_baselines("suite-a")
    assert baselines["case-1"] == "run-002"


@pytest.mark.asyncio
async def test_sqlite_baselines_empty_suite(sqlite_store):
    assert await sqlite_store.get_baselines("no-such-suite") == {}


@pytest.mark.asyncio
async def test_sqlite_save_list_get_eval_result(sqlite_store):
    result = _FakeEvalResult("suite-a", "/path/suite.yaml")
    result_id = await sqlite_store.save_eval_result(result)

    assert result_id.startswith("eval_")

    listing = await sqlite_store.list_eval_results()
    assert any(r["suite_name"] == "suite-a" for r in listing)

    fetched = await sqlite_store.get_eval_result(result_id)
    assert fetched is not None
    assert fetched["suite_name"] == "suite-a"
    assert isinstance(fetched["payload"], dict)


@pytest.mark.asyncio
async def test_sqlite_list_eval_results_suite_filter(sqlite_store):
    await sqlite_store.save_eval_result(_FakeEvalResult("suite-a"))
    await sqlite_store.save_eval_result(_FakeEvalResult("suite-b"))

    a_results = await sqlite_store.list_eval_results(suite_name="suite-a")
    assert all(r["suite_name"] == "suite-a" for r in a_results)
    assert len(a_results) >= 1


@pytest.mark.asyncio
async def test_sqlite_get_eval_result_missing(sqlite_store):
    assert await sqlite_store.get_eval_result("eval_nonexistent") is None


@pytest.mark.asyncio
async def test_sqlite_run_new_fields_round_trip(sqlite_store):
    run = _make_run("run-100", eval_suite_id="suite-x", eval_case_id="case-y", source="eval")
    await sqlite_store.create_run(run)

    fetched = await sqlite_store.get_run("run-100")
    assert fetched is not None
    assert fetched.eval_suite_id == "suite-x"
    assert fetched.eval_case_id == "case-y"
    assert fetched.source == "eval"


@pytest.mark.asyncio
async def test_sqlite_run_new_fields_null_safe(sqlite_store):
    run = _make_run("run-200")
    await sqlite_store.create_run(run)

    fetched = await sqlite_store.get_run("run-200")
    assert fetched is not None
    assert fetched.eval_suite_id is None
    assert fetched.eval_case_id is None
    assert fetched.source is None


@pytest.mark.asyncio
async def test_sqlite_run_new_fields_in_list(sqlite_store):
    run = _make_run("run-300", eval_suite_id="s", eval_case_id="c", source="otel-import")
    await sqlite_store.create_run(run)

    runs = await sqlite_store.list_runs()
    target = next((r for r in runs if r.run_id == "run-300"), None)
    assert target is not None
    assert target.source == "otel-import"
