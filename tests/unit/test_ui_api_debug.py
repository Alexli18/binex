"""Tests for the debug API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from binex.models.artifact import Artifact, Lineage
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


def _make_run(run_id: str = "run-1", status: str = "completed") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-workflow",
        status=status,
        started_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 0, 0, 10, tzinfo=UTC),
        total_nodes=3,
        completed_nodes=2,
        failed_nodes=1,
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


def _make_artifact(
    run_id: str = "run-1",
    art_id: str = "art-1",
    produced_by: str = "node_a",
    art_type: str = "text",
    content: str = "hello",
) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=produced_by),
    )


@pytest.mark.asyncio
async def test_debug_basic(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run())
    await exec_store.record(_make_record(task_id="node_a", rec_id="rec-1"))
    await exec_store.record(
        _make_record(task_id="node_b", status=TaskStatus.FAILED, error="timeout", rec_id="rec-2"),
    )
    await art_store.store(_make_artifact(art_id="art-1", produced_by="node_a"))

    with patch("binex.ui.api.debug._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/debug")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["status"] == "completed"
    assert data["workflow_name"] == "test-workflow"
    assert len(data["nodes"]) == 2

    node_a = next(n for n in data["nodes"] if n["node_id"] == "node_a")
    assert node_a["status"] == "completed"
    assert node_a["duration_s"] == 1.0
    assert node_a["error"] is None
    assert len(node_a["artifacts"]) == 1
    assert node_a["artifacts"][0]["id"] == "art-1"

    node_b = next(n for n in data["nodes"] if n["node_id"] == "node_b")
    assert node_b["status"] == "failed"
    assert node_b["error"] == "timeout"
    assert node_b["artifacts"] == []


@pytest.mark.asyncio
async def test_debug_errors_only(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run())
    await exec_store.record(_make_record(task_id="node_a", rec_id="rec-1"))
    await exec_store.record(
        _make_record(task_id="node_b", status=TaskStatus.FAILED, error="boom", rec_id="rec-2"),
    )

    with patch("binex.ui.api.debug._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/debug?errors_only=true")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["node_id"] == "node_b"


@pytest.mark.asyncio
async def test_debug_node_filter(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run())
    await exec_store.record(_make_record(task_id="node_a", rec_id="rec-1"))
    await exec_store.record(_make_record(task_id="node_b", rec_id="rec-2"))

    with patch("binex.ui.api.debug._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/debug?node=node_a")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["node_id"] == "node_a"


@pytest.mark.asyncio
async def test_debug_not_found(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.debug._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/nonexistent/debug")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_debug_no_records(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run())

    with patch("binex.ui.api.debug._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/debug")

    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
