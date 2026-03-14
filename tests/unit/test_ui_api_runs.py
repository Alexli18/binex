"""Tests for the runs API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from binex.models.execution import ExecutionRecord, RunSummary
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


def _make_run(run_id: str = "run-1", **kwargs) -> RunSummary:
    defaults = dict(
        run_id=run_id,
        workflow_name="test-workflow",
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        total_nodes=3,
        completed_nodes=3,
    )
    defaults.update(kwargs)
    return RunSummary(**defaults)


def _make_record(run_id: str = "run-1", task_id: str = "task-1", **kwargs) -> ExecutionRecord:
    defaults = dict(
        id="rec-1",
        run_id=run_id,
        task_id=task_id,
        agent_id="llm://openai/gpt-4",
        status="completed",
        latency_ms=150,
        trace_id="trace-1",
    )
    defaults.update(kwargs)
    return ExecutionRecord(**defaults)


@pytest.mark.asyncio
async def test_list_runs(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run("run-1"))
    await exec_store.create_run(_make_run("run-2", workflow_name="other"))

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs")

    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert len(data["runs"]) == 2
    run_ids = {r["run_id"] for r in data["runs"]}
    assert run_ids == {"run-1", "run-2"}


@pytest.mark.asyncio
async def test_list_runs_empty(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs")

    assert resp.status_code == 200
    assert resp.json() == {"runs": []}


@pytest.mark.asyncio
async def test_get_run(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run("run-1"))

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["workflow_name"] == "test-workflow"
    assert data["status"] == "completed"
    assert data["total_nodes"] == 3


@pytest.mark.asyncio
async def test_get_run_not_found(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/nonexistent")

    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] == "Run 'nonexistent' not found"


@pytest.mark.asyncio
async def test_get_records(client, stores):
    exec_store, art_store = stores
    await exec_store.create_run(_make_run("run-1"))
    await exec_store.record(_make_record("run-1", "task-1", id="rec-1"))
    await exec_store.record(_make_record("run-1", "task-2", id="rec-2"))

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/records")

    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert len(data["records"]) == 2
    task_ids = {r["task_id"] for r in data["records"]}
    assert task_ids == {"task-1", "task-2"}


@pytest.mark.asyncio
async def test_get_records_empty(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/records")

    assert resp.status_code == 200
    assert resp.json() == {"records": []}


@pytest.mark.asyncio
async def test_cancel_run_running(client, stores):
    """POST /runs/{run_id}/cancel on a running run returns 200."""
    exec_store, art_store = stores
    await exec_store.create_run(_make_run("run-1", status="running"))

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/runs/run-1/cancel")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["status"] == "cancelled"

    # Verify status was actually updated in the store
    updated = await exec_store.get_run("run-1")
    assert updated is not None
    assert updated.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_run_completed(client, stores):
    """POST /runs/{run_id}/cancel on a completed run returns 409."""
    exec_store, art_store = stores
    await exec_store.create_run(_make_run("run-1", status="completed"))

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/runs/run-1/cancel")

    assert resp.status_code == 409
    data = resp.json()
    assert "not running" in data["error"]


@pytest.mark.asyncio
async def test_cancel_run_not_found(client, stores):
    """POST /runs/{run_id}/cancel on nonexistent run returns 404."""
    exec_store, art_store = stores

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/runs/nonexistent/cancel")

    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["error"]


@pytest.mark.asyncio
async def test_create_run(client, stores, tmp_path):
    """POST /runs with valid workflow_path returns 201 with run_id."""
    exec_store, art_store = stores
    workflow_file = tmp_path / "test.yaml"
    workflow_file.write_text("name: test\nnodes: []\n")

    mock_result = {"run_id": "run_abc123", "status": "completed"}
    with patch("binex.ui.api.runs._execute_workflow", return_value=mock_result):
        resp = await client.post(
            "/api/v1/runs",
            json={"workflow_path": str(workflow_file)},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["run_id"] == "run_abc123"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_create_run_not_found(client, stores):
    """POST /runs with nonexistent workflow returns 404."""
    exec_store, art_store = stores

    with patch("binex.ui.api.runs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/runs",
            json={"workflow_path": "/nonexistent/workflow.yaml"},
        )

    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["error"]
