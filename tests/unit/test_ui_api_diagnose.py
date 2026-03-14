"""Tests for the diagnose API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
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


def _make_run(run_id: str = "run-1", status: str = "failed", total_cost: float = 0.42) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-workflow",
        status=status,
        started_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
        total_nodes=3,
        completed_nodes=1,
        failed_nodes=1,
        total_cost=total_cost,
    )


def _make_record(
    run_id: str = "run-1",
    task_id: str = "node_a",
    status: TaskStatus = TaskStatus.COMPLETED,
    latency_ms: int = 1000,
    error: str | None = None,
    rec_id: str = "rec-1",
) -> ExecutionRecord:
    return ExecutionRecord(
        id=rec_id,
        run_id=run_id,
        task_id=task_id,
        agent_id=f"llm://{task_id}",
        status=status,
        latency_ms=latency_ms,
        timestamp=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        trace_id="trace-1",
        error=error,
    )


@pytest.mark.asyncio
async def test_diagnose_with_failure(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run())
    await exec_store.record(_make_record(task_id="node_a", rec_id="rec-1"))
    await exec_store.record(
        _make_record(
            task_id="node_b", status=TaskStatus.FAILED,
            error="Connection refused", rec_id="rec-2",
        ),
    )

    with patch("binex.ui.api.diagnose._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/diagnose")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["status"] == "issues_found"
    assert data["severity"] == "HIGH"
    assert data["total_cost"] == 0.42

    assert len(data["root_causes"]) == 1
    rc = data["root_causes"][0]
    assert rc["node_id"] == "node_b"
    assert "Connection refused" in rc["error"]
    assert rc["status"] == "failed"

    assert len(data["recommendations"]) >= 1


@pytest.mark.asyncio
async def test_diagnose_clean_run(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run(status="completed", total_cost=0.1))
    await exec_store.record(_make_record(task_id="node_a", rec_id="rec-1"))
    await exec_store.record(_make_record(task_id="node_b", rec_id="rec-2"))

    with patch("binex.ui.api.diagnose._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/diagnose")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "clean"
    assert data["severity"] == "NONE"
    assert data["root_causes"] == []
    assert data["recommendations"] == []


@pytest.mark.asyncio
async def test_diagnose_not_found(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.diagnose._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/nonexistent/diagnose")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diagnose_latency_anomalies(client, stores):
    """Latency anomalies detected with HIGH severity when a skipped node triggers analysis."""
    exec_store, art_store = stores
    await exec_store.create_run(_make_run(status="completed", total_cost=0.0))

    # Two fast nodes, one slow, and one skipped to trigger full analysis
    await exec_store.record(_make_record(task_id="fast_a", latency_ms=100, rec_id="r1"))
    await exec_store.record(_make_record(task_id="fast_b", latency_ms=100, rec_id="r2"))
    await exec_store.record(_make_record(task_id="slow_c", latency_ms=1000, rec_id="r3"))
    await exec_store.record(
        _make_record(task_id="skipped_d", latency_ms=0, rec_id="r4",
                     status=TaskStatus.FAILED, error="budget exceeded"),
    )

    with patch("binex.ui.api.diagnose._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/diagnose")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "issues_found"
    # Has root cause (failed node) so severity is HIGH
    assert data["severity"] == "HIGH"
    assert len(data["root_causes"]) >= 1
    # Latency anomalies: slow_c is 10x median of [100, 100, 1000] = 100ms
    assert len(data["latency_anomalies"]) >= 1
