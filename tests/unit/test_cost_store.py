"""Comprehensive tests for cost storage methods in SqliteExecutionStore and InMemoryExecutionStore."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime

import pytest

from binex.models.cost import CostRecord, RunCostSummary
from binex.models.execution import RunSummary
from binex.stores.backends.memory import InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cost_record(
    run_id: str = "run-1",
    task_id: str = "task-1",
    cost: float = 0.01,
    source: str = "llm_tokens",
    model: str | None = "gpt-4",
    prompt_tokens: int | None = 100,
    completion_tokens: int | None = 50,
) -> CostRecord:
    return CostRecord(
        id=str(uuid.uuid4()),
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        currency="USD",
        source=source,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        model=model,
        timestamp=datetime.now(UTC),
    )


def _make_run_summary(
    run_id: str = "run-1",
    total_cost: float = 0.0,
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-workflow",
        status="completed",
        started_at=datetime.now(UTC),
        total_nodes=3,
        completed_nodes=3,
        total_cost=total_cost,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def sqlite_store():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    store = SqliteExecutionStore(path)
    await store.initialize()
    yield store
    await store.close()
    os.unlink(path)


@pytest.fixture
def memory_store():
    return InMemoryExecutionStore()


# ---------------------------------------------------------------------------
# SqliteExecutionStore — record_cost
# ---------------------------------------------------------------------------

class TestSqliteRecordCost:
    @pytest.mark.asyncio
    async def test_record_single_cost(self, sqlite_store: SqliteExecutionStore):
        record = _make_cost_record()
        await sqlite_store.record_cost(record)
        costs = await sqlite_store.list_costs("run-1")
        assert len(costs) == 1
        assert costs[0].id == record.id
        assert costs[0].cost == 0.01

    @pytest.mark.asyncio
    async def test_record_cost_preserves_all_fields(self, sqlite_store: SqliteExecutionStore):
        record = _make_cost_record(
            cost=0.05,
            source="agent_report",
            model="claude-3-opus",
            prompt_tokens=200,
            completion_tokens=80,
        )
        await sqlite_store.record_cost(record)
        costs = await sqlite_store.list_costs("run-1")
        stored = costs[0]
        assert stored.run_id == "run-1"
        assert stored.task_id == "task-1"
        assert stored.cost == 0.05
        assert stored.currency == "USD"
        assert stored.source == "agent_report"
        assert stored.model == "claude-3-opus"
        assert stored.prompt_tokens == 200
        assert stored.completion_tokens == 80

    @pytest.mark.asyncio
    async def test_record_cost_with_none_tokens(self, sqlite_store: SqliteExecutionStore):
        record = _make_cost_record(
            source="local",
            prompt_tokens=None,
            completion_tokens=None,
            model=None,
        )
        await sqlite_store.record_cost(record)
        costs = await sqlite_store.list_costs("run-1")
        assert costs[0].prompt_tokens is None
        assert costs[0].completion_tokens is None
        assert costs[0].model is None

    @pytest.mark.asyncio
    async def test_record_multiple_costs_same_run(self, sqlite_store: SqliteExecutionStore):
        for i in range(5):
            await sqlite_store.record_cost(
                _make_cost_record(cost=0.01 * (i + 1), task_id=f"task-{i}")
            )
        costs = await sqlite_store.list_costs("run-1")
        assert len(costs) == 5

    @pytest.mark.asyncio
    async def test_record_cost_zero_cost(self, sqlite_store: SqliteExecutionStore):
        record = _make_cost_record(cost=0.0, source="local")
        await sqlite_store.record_cost(record)
        costs = await sqlite_store.list_costs("run-1")
        assert costs[0].cost == 0.0


# ---------------------------------------------------------------------------
# SqliteExecutionStore — list_costs
# ---------------------------------------------------------------------------

class TestSqliteListCosts:
    @pytest.mark.asyncio
    async def test_list_costs_empty_run(self, sqlite_store: SqliteExecutionStore):
        costs = await sqlite_store.list_costs("nonexistent-run")
        assert costs == []

    @pytest.mark.asyncio
    async def test_list_costs_filters_by_run_id(self, sqlite_store: SqliteExecutionStore):
        await sqlite_store.record_cost(_make_cost_record(run_id="run-A"))
        await sqlite_store.record_cost(_make_cost_record(run_id="run-B"))
        await sqlite_store.record_cost(_make_cost_record(run_id="run-A"))

        costs_a = await sqlite_store.list_costs("run-A")
        costs_b = await sqlite_store.list_costs("run-B")
        assert len(costs_a) == 2
        assert len(costs_b) == 1

    @pytest.mark.asyncio
    async def test_list_costs_ordered_by_timestamp(self, sqlite_store: SqliteExecutionStore):
        ts1 = datetime(2026, 1, 1, 0, 0, 0)
        ts2 = datetime(2026, 1, 1, 0, 0, 1)
        ts3 = datetime(2026, 1, 1, 0, 0, 2)
        # Insert out of order
        for ts, tid in [(ts3, "c"), (ts1, "a"), (ts2, "b")]:
            r = _make_cost_record(task_id=tid)
            r.timestamp = ts
            await sqlite_store.record_cost(r)

        costs = await sqlite_store.list_costs("run-1")
        assert [c.task_id for c in costs] == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# SqliteExecutionStore — get_run_cost_summary
# ---------------------------------------------------------------------------

class TestSqliteGetRunCostSummary:
    @pytest.mark.asyncio
    async def test_empty_run_returns_zero_total(self, sqlite_store: SqliteExecutionStore):
        summary = await sqlite_store.get_run_cost_summary("empty-run")
        assert summary.run_id == "empty-run"
        assert summary.total_cost == 0.0
        assert summary.node_costs == {}
        assert summary.currency == "USD"

    @pytest.mark.asyncio
    async def test_single_record_summary(self, sqlite_store: SqliteExecutionStore):
        await sqlite_store.record_cost(_make_cost_record(cost=0.05, task_id="nodeA"))
        summary = await sqlite_store.get_run_cost_summary("run-1")
        assert summary.total_cost == pytest.approx(0.05)
        assert summary.node_costs == {"nodeA": pytest.approx(0.05)}

    @pytest.mark.asyncio
    async def test_multiple_records_aggregate(self, sqlite_store: SqliteExecutionStore):
        await sqlite_store.record_cost(_make_cost_record(cost=0.10, task_id="A"))
        await sqlite_store.record_cost(_make_cost_record(cost=0.20, task_id="B"))
        await sqlite_store.record_cost(_make_cost_record(cost=0.30, task_id="C"))
        summary = await sqlite_store.get_run_cost_summary("run-1")
        assert summary.total_cost == pytest.approx(0.60)
        assert len(summary.node_costs) == 3

    @pytest.mark.asyncio
    async def test_node_costs_group_by_task_id(self, sqlite_store: SqliteExecutionStore):
        await sqlite_store.record_cost(_make_cost_record(cost=0.10, task_id="nodeX"))
        await sqlite_store.record_cost(_make_cost_record(cost=0.15, task_id="nodeX"))
        await sqlite_store.record_cost(_make_cost_record(cost=0.05, task_id="nodeY"))
        summary = await sqlite_store.get_run_cost_summary("run-1")
        assert summary.total_cost == pytest.approx(0.30)
        assert summary.node_costs["nodeX"] == pytest.approx(0.25)
        assert summary.node_costs["nodeY"] == pytest.approx(0.05)

    @pytest.mark.asyncio
    async def test_summary_only_includes_target_run(self, sqlite_store: SqliteExecutionStore):
        await sqlite_store.record_cost(_make_cost_record(run_id="run-1", cost=0.10))
        await sqlite_store.record_cost(_make_cost_record(run_id="run-2", cost=0.50))
        summary = await sqlite_store.get_run_cost_summary("run-1")
        assert summary.total_cost == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# SqliteExecutionStore — total_cost column in runs table
# ---------------------------------------------------------------------------

class TestSqliteTotalCostColumn:
    @pytest.mark.asyncio
    async def test_create_run_with_total_cost(self, sqlite_store: SqliteExecutionStore):
        run = _make_run_summary(run_id="run-cost-1", total_cost=1.23)
        await sqlite_store.create_run(run)
        retrieved = await sqlite_store.get_run("run-cost-1")
        assert retrieved is not None
        assert retrieved.total_cost == pytest.approx(1.23)

    @pytest.mark.asyncio
    async def test_create_run_default_total_cost_zero(self, sqlite_store: SqliteExecutionStore):
        run = _make_run_summary(run_id="run-zero")
        await sqlite_store.create_run(run)
        retrieved = await sqlite_store.get_run("run-zero")
        assert retrieved is not None
        assert retrieved.total_cost == 0.0

    @pytest.mark.asyncio
    async def test_update_run_total_cost(self, sqlite_store: SqliteExecutionStore):
        run = _make_run_summary(run_id="run-upd", total_cost=0.0)
        await sqlite_store.create_run(run)
        run.total_cost = 2.50
        await sqlite_store.update_run(run)
        retrieved = await sqlite_store.get_run("run-upd")
        assert retrieved is not None
        assert retrieved.total_cost == pytest.approx(2.50)

    @pytest.mark.asyncio
    async def test_list_runs_includes_total_cost(self, sqlite_store: SqliteExecutionStore):
        await sqlite_store.create_run(_make_run_summary(run_id="r1", total_cost=0.5))
        await sqlite_store.create_run(_make_run_summary(run_id="r2", total_cost=1.5))
        runs = await sqlite_store.list_runs()
        cost_map = {r.run_id: r.total_cost for r in runs}
        assert cost_map["r1"] == pytest.approx(0.5)
        assert cost_map["r2"] == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# InMemoryExecutionStore — record_cost
# ---------------------------------------------------------------------------

class TestMemoryRecordCost:
    @pytest.mark.asyncio
    async def test_record_single_cost(self, memory_store: InMemoryExecutionStore):
        record = _make_cost_record()
        await memory_store.record_cost(record)
        costs = await memory_store.list_costs("run-1")
        assert len(costs) == 1
        assert costs[0].id == record.id

    @pytest.mark.asyncio
    async def test_record_cost_preserves_all_fields(self, memory_store: InMemoryExecutionStore):
        record = _make_cost_record(
            cost=0.07,
            source="llm_tokens_unavailable",
            model="gpt-4o",
            prompt_tokens=300,
            completion_tokens=120,
        )
        await memory_store.record_cost(record)
        costs = await memory_store.list_costs("run-1")
        stored = costs[0]
        assert stored.cost == 0.07
        assert stored.source == "llm_tokens_unavailable"
        assert stored.model == "gpt-4o"
        assert stored.prompt_tokens == 300
        assert stored.completion_tokens == 120

    @pytest.mark.asyncio
    async def test_record_multiple_costs(self, memory_store: InMemoryExecutionStore):
        for _ in range(3):
            await memory_store.record_cost(_make_cost_record())
        costs = await memory_store.list_costs("run-1")
        assert len(costs) == 3


# ---------------------------------------------------------------------------
# InMemoryExecutionStore — list_costs
# ---------------------------------------------------------------------------

class TestMemoryListCosts:
    @pytest.mark.asyncio
    async def test_list_costs_empty(self, memory_store: InMemoryExecutionStore):
        costs = await memory_store.list_costs("no-such-run")
        assert costs == []

    @pytest.mark.asyncio
    async def test_list_costs_filters_by_run_id(self, memory_store: InMemoryExecutionStore):
        await memory_store.record_cost(_make_cost_record(run_id="run-X"))
        await memory_store.record_cost(_make_cost_record(run_id="run-Y"))
        await memory_store.record_cost(_make_cost_record(run_id="run-X"))

        assert len(await memory_store.list_costs("run-X")) == 2
        assert len(await memory_store.list_costs("run-Y")) == 1


# ---------------------------------------------------------------------------
# InMemoryExecutionStore — get_run_cost_summary
# ---------------------------------------------------------------------------

class TestMemoryGetRunCostSummary:
    @pytest.mark.asyncio
    async def test_empty_run_returns_zero_total(self, memory_store: InMemoryExecutionStore):
        summary = await memory_store.get_run_cost_summary("empty")
        assert summary.run_id == "empty"
        assert summary.total_cost == 0.0
        assert summary.node_costs == {}

    @pytest.mark.asyncio
    async def test_multiple_records_aggregate(self, memory_store: InMemoryExecutionStore):
        await memory_store.record_cost(_make_cost_record(cost=0.10, task_id="A"))
        await memory_store.record_cost(_make_cost_record(cost=0.20, task_id="B"))
        await memory_store.record_cost(_make_cost_record(cost=0.30, task_id="C"))
        summary = await memory_store.get_run_cost_summary("run-1")
        assert summary.total_cost == pytest.approx(0.60)

    @pytest.mark.asyncio
    async def test_node_costs_group_by_task_id(self, memory_store: InMemoryExecutionStore):
        await memory_store.record_cost(_make_cost_record(cost=0.10, task_id="nodeX"))
        await memory_store.record_cost(_make_cost_record(cost=0.15, task_id="nodeX"))
        await memory_store.record_cost(_make_cost_record(cost=0.05, task_id="nodeY"))
        summary = await memory_store.get_run_cost_summary("run-1")
        assert summary.node_costs["nodeX"] == pytest.approx(0.25)
        assert summary.node_costs["nodeY"] == pytest.approx(0.05)

    @pytest.mark.asyncio
    async def test_summary_only_includes_target_run(self, memory_store: InMemoryExecutionStore):
        await memory_store.record_cost(_make_cost_record(run_id="run-1", cost=0.10))
        await memory_store.record_cost(_make_cost_record(run_id="run-2", cost=0.50))
        summary = await memory_store.get_run_cost_summary("run-1")
        assert summary.total_cost == pytest.approx(0.10)

    @pytest.mark.asyncio
    async def test_summary_returns_run_cost_summary_type(self, memory_store: InMemoryExecutionStore):
        summary = await memory_store.get_run_cost_summary("any")
        assert isinstance(summary, RunCostSummary)


# ---------------------------------------------------------------------------
# Cross-store consistency: both stores produce identical summaries
# ---------------------------------------------------------------------------

class TestCrossStoreConsistency:
    @pytest.mark.asyncio
    async def test_both_stores_produce_same_summary(self, sqlite_store, memory_store):
        records = [
            _make_cost_record(cost=0.10, task_id="A"),
            _make_cost_record(cost=0.20, task_id="A"),
            _make_cost_record(cost=0.05, task_id="B"),
        ]
        for r in records:
            await sqlite_store.record_cost(r)
            await memory_store.record_cost(r)

        s_sqlite = await sqlite_store.get_run_cost_summary("run-1")
        s_memory = await memory_store.get_run_cost_summary("run-1")

        assert s_sqlite.total_cost == pytest.approx(s_memory.total_cost)
        assert s_sqlite.node_costs.keys() == s_memory.node_costs.keys()
        for key in s_sqlite.node_costs:
            assert s_sqlite.node_costs[key] == pytest.approx(s_memory.node_costs[key])
