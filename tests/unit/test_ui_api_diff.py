"""Tests for the diff API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
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


def _make_run(run_id: str, status: str = "completed", workflow: str = "test-wf") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name=workflow,
        status=status,
        total_nodes=2,
        completed_nodes=2,
    )


def _make_record(
    run_id: str, task_id: str,
    status: TaskStatus = TaskStatus.COMPLETED,
    latency_ms: int = 100,
    output_refs: list[str] | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"{run_id}-{task_id}",
        run_id=run_id,
        task_id=task_id,
        agent_id="local://echo",
        status=status,
        latency_ms=latency_ms,
        output_artifact_refs=output_refs or [],
        trace_id="trace-1",
    )


def _make_artifact(art_id: str, run_id: str, content: str) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type="text",
        content=content,
        lineage=Lineage(produced_by="test", derived_from=[]),
    )


def _make_cost(
    run_id: str, task_id: str, cost: float, cost_id: str = "c1",
) -> CostRecord:
    return CostRecord(
        id=cost_id,
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        source="llm_tokens",
        model="gpt-4",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_diff_basic(client, stores):
    """Diff two runs with identical nodes but different statuses."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("run-a"))
    await exec_store.create_run(_make_run("run-b"))

    await exec_store.record(_make_record("run-a", "node1", latency_ms=100))
    await exec_store.record(_make_record("run-a", "node2", latency_ms=200))
    await exec_store.record(_make_record("run-b", "node1", latency_ms=150))
    await exec_store.record(
        _make_record("run-b", "node2", status=TaskStatus.FAILED, latency_ms=300),
    )

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "run-a", "run_b": "run-b"})

    assert resp.status_code == 200
    data = resp.json()

    assert data["run_a"]["run_id"] == "run-a"
    assert data["run_b"]["run_id"] == "run-b"
    assert data["run_a"]["node_count"] == 2
    assert data["run_b"]["node_count"] == 2
    assert len(data["node_diffs"]) == 2

    node2 = next(d for d in data["node_diffs"] if d["node_id"] == "node2")
    assert node2["status_a"] == "completed"
    assert node2["status_b"] == "failed"
    assert node2["duration_a"] == 200
    assert node2["duration_b"] == 300


@pytest.mark.asyncio
async def test_diff_with_artifacts(client, stores):
    """Diff two runs with differing artifact content produces unified diff."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("run-a"))
    await exec_store.create_run(_make_run("run-b"))

    await art_store.store(_make_artifact("art-a1", "run-a", "Hello World"))
    await art_store.store(_make_artifact("art-b1", "run-b", "Hello Earth"))

    await exec_store.record(
        _make_record("run-a", "node1", output_refs=["art-a1"]),
    )
    await exec_store.record(
        _make_record("run-b", "node1", output_refs=["art-b1"]),
    )

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "run-a", "run_b": "run-b"})

    assert resp.status_code == 200
    data = resp.json()
    node1 = data["node_diffs"][0]
    assert node1["artifact_diff"] is not None
    assert "Hello World" in node1["artifact_diff"]
    assert "Hello Earth" in node1["artifact_diff"]


@pytest.mark.asyncio
async def test_diff_identical_artifacts(client, stores):
    """Diff with identical artifacts produces null artifact_diff."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("run-a"))
    await exec_store.create_run(_make_run("run-b"))

    await art_store.store(_make_artifact("art-a1", "run-a", "Same content"))
    await art_store.store(_make_artifact("art-b1", "run-b", "Same content"))

    await exec_store.record(
        _make_record("run-a", "node1", output_refs=["art-a1"]),
    )
    await exec_store.record(
        _make_record("run-b", "node1", output_refs=["art-b1"]),
    )

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "run-a", "run_b": "run-b"})

    assert resp.status_code == 200
    node1 = resp.json()["node_diffs"][0]
    assert node1["artifact_diff"] is None


@pytest.mark.asyncio
async def test_diff_with_costs(client, stores):
    """Diff includes cost data per node."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("run-a"))
    await exec_store.create_run(_make_run("run-b"))

    await exec_store.record(_make_record("run-a", "node1"))
    await exec_store.record(_make_record("run-b", "node1"))

    await exec_store.record_cost(_make_cost("run-a", "node1", 0.05, "ca1"))
    await exec_store.record_cost(_make_cost("run-b", "node1", 0.10, "cb1"))

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "run-a", "run_b": "run-b"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_a"]["total_cost"] == pytest.approx(0.05)
    assert data["run_b"]["total_cost"] == pytest.approx(0.10)

    node1 = data["node_diffs"][0]
    assert node1["cost_a"] == pytest.approx(0.05)
    assert node1["cost_b"] == pytest.approx(0.10)


@pytest.mark.asyncio
async def test_diff_run_not_found(client, stores):
    """Diff returns 404 when a run is not found."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("run-a"))

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "run-a", "run_b": "missing"})

    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]


@pytest.mark.asyncio
async def test_diff_both_missing(client, stores):
    """Diff returns 404 when run_a is not found."""
    exec_store, art_store = stores

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "missing", "run_b": "also-missing"})

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_diff_empty_runs(client, stores):
    """Diff with runs that have no records returns empty node_diffs."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("run-a"))
    await exec_store.create_run(_make_run("run-b"))

    with patch("binex.ui.api.diff._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post("/api/v1/diff", json={"run_a": "run-a", "run_b": "run-b"})

    assert resp.status_code == 200
    assert resp.json()["node_diffs"] == []
