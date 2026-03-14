"""Tests for the trace API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest

from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.ui.server import create_app


@pytest.fixture
def stores():
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    return exec_store, art_store


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_run(
    run_id: str = "run-1",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-workflow",
        status="completed",
        started_at=started_at or datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        completed_at=completed_at or datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
        total_nodes=3,
        completed_nodes=3,
    )


def _make_record(
    run_id: str = "run-1",
    task_id: str = "node_a",
    latency_ms: int = 1000,
    timestamp: datetime | None = None,
    rec_id: str = "rec-1",
    status: TaskStatus = TaskStatus.COMPLETED,
    error: str | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        id=rec_id,
        run_id=run_id,
        task_id=task_id,
        agent_id=f"llm://{task_id}",
        status=status,
        latency_ms=latency_ms,
        timestamp=timestamp or datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        trace_id="trace-1",
        error=error,
    )


@pytest.mark.asyncio
async def test_trace_basic(client, stores):
    exec_store, art_store = stores
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    await exec_store.create_run(_make_run(started_at=start, completed_at=start + timedelta(seconds=10)))
    # timestamp = end time (when record was created), offset = end - duration - run_start
    # node_a: started at +1s, ran for 2s, ended at +3s
    await exec_store.record(
        _make_record(task_id="node_a", latency_ms=2000, timestamp=start + timedelta(seconds=3), rec_id="r1"),
    )
    # node_b: started at +4s, ran for 3s, ended at +7s
    await exec_store.record(
        _make_record(task_id="node_b", latency_ms=3000, timestamp=start + timedelta(seconds=7), rec_id="r2"),
    )

    with patch("binex.ui.api.trace._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/trace")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["status"] == "completed"
    assert data["total_duration_s"] == 10.0
    assert len(data["timeline"]) == 2

    t0 = data["timeline"][0]
    assert t0["node_id"] == "node_a"
    assert t0["duration_s"] == 2.0
    assert t0["offset_s"] == 1.0

    t1 = data["timeline"][1]
    assert t1["node_id"] == "node_b"
    assert t1["offset_s"] == 4.0


@pytest.mark.asyncio
async def test_trace_anomalies(client, stores):
    exec_store, art_store = stores
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    await exec_store.create_run(_make_run(started_at=start, completed_at=start + timedelta(seconds=20)))

    # Two normal nodes (1s each) and one slow node (10s) — ratio = 10/1 = 10x > 2x threshold
    await exec_store.record(
        _make_record(task_id="fast_a", latency_ms=1000, timestamp=start + timedelta(seconds=1), rec_id="r1"),
    )
    await exec_store.record(
        _make_record(task_id="fast_b", latency_ms=1000, timestamp=start + timedelta(seconds=2), rec_id="r2"),
    )
    await exec_store.record(
        _make_record(task_id="slow_c", latency_ms=10000, timestamp=start + timedelta(seconds=3), rec_id="r3"),
    )

    with patch("binex.ui.api.trace._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/trace")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["anomalies"]) == 1
    anomaly = data["anomalies"][0]
    assert anomaly["node_id"] == "slow_c"
    assert anomaly["duration_s"] == 10.0
    assert anomaly["ratio"] == 10.0


@pytest.mark.asyncio
async def test_trace_not_found(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.trace._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/nonexistent/trace")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_trace_no_records(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run())

    with patch("binex.ui.api.trace._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/trace")

    assert resp.status_code == 200
    data = resp.json()
    assert data["timeline"] == []
    assert data["anomalies"] == []


@pytest.mark.asyncio
async def test_trace_no_anomalies_when_similar_durations(client, stores):
    """No anomalies when all nodes have similar durations."""
    exec_store, art_store = stores
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    await exec_store.create_run(_make_run(started_at=start, completed_at=start + timedelta(seconds=5)))

    await exec_store.record(
        _make_record(task_id="a", latency_ms=1000, timestamp=start + timedelta(seconds=1), rec_id="r1"),
    )
    await exec_store.record(
        _make_record(task_id="b", latency_ms=1200, timestamp=start + timedelta(seconds=2), rec_id="r2"),
    )

    with patch("binex.ui.api.trace._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/trace")

    assert resp.status_code == 200
    assert resp.json()["anomalies"] == []
