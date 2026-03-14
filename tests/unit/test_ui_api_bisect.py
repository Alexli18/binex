"""Tests for the bisect API endpoint."""

from __future__ import annotations

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
    error: str | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"{run_id}-{task_id}",
        run_id=run_id,
        task_id=task_id,
        agent_id="local://echo",
        status=status,
        latency_ms=latency_ms,
        output_artifact_refs=output_refs or [],
        error=error,
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


@pytest.mark.asyncio
async def test_bisect_status_divergence(client, stores):
    """Bisect finds divergence when bad run has a failed node."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("good", status="completed"))
    await exec_store.create_run(_make_run("bad", status="failed"))

    await exec_store.record(_make_record("good", "node1"))
    await exec_store.record(_make_record("good", "node2"))
    await exec_store.record(_make_record("bad", "node1"))
    await exec_store.record(
        _make_record("bad", "node2", status=TaskStatus.FAILED, error="timeout"),
    )

    with patch("binex.ui.api.bisect._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/bisect",
            json={"good_run": "good", "bad_run": "bad"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["good_run"] == "good"
    assert data["bad_run"] == "bad"
    assert data["divergence_node"] == "node2"
    assert data["divergence_index"] == 1
    assert data["details"]["node_id"] == "node2"
    assert data["details"]["good_status"] == "completed"
    assert data["details"]["bad_status"] == "failed"


@pytest.mark.asyncio
async def test_bisect_no_divergence(client, stores):
    """Bisect returns null divergence when runs are identical."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("good"))
    await exec_store.create_run(_make_run("bad"))

    await exec_store.record(_make_record("good", "node1"))
    await exec_store.record(_make_record("bad", "node1"))

    with patch("binex.ui.api.bisect._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/bisect",
            json={"good_run": "good", "bad_run": "bad"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["divergence_node"] is None
    assert data["divergence_index"] is None
    assert data["details"] is None


@pytest.mark.asyncio
async def test_bisect_content_divergence(client, stores):
    """Bisect detects content divergence below threshold."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("good"))
    await exec_store.create_run(_make_run("bad"))

    await art_store.store(_make_artifact("art-g1", "good", "The quick brown fox"))
    await art_store.store(_make_artifact("art-b1", "bad", "Something completely different"))

    await exec_store.record(
        _make_record("good", "node1", output_refs=["art-g1"]),
    )
    await exec_store.record(
        _make_record("bad", "node1", output_refs=["art-b1"]),
    )

    with patch("binex.ui.api.bisect._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/bisect",
            json={"good_run": "good", "bad_run": "bad", "threshold": 0.9},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["divergence_node"] == "node1"
    assert data["similarity"] is not None


@pytest.mark.asyncio
async def test_bisect_run_not_found(client, stores):
    """Bisect returns 404 when a run doesn't exist."""
    exec_store, art_store = stores

    with patch("binex.ui.api.bisect._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/bisect",
            json={"good_run": "missing", "bad_run": "also-missing"},
        )

    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]


@pytest.mark.asyncio
async def test_bisect_workflow_mismatch(client, stores):
    """Bisect returns 404 when workflows don't match."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("good", workflow="wf-a"))
    await exec_store.create_run(_make_run("bad", workflow="wf-b"))

    with patch("binex.ui.api.bisect._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/bisect",
            json={"good_run": "good", "bad_run": "bad"},
        )

    assert resp.status_code == 404
    assert "don't match" in resp.json()["error"]


@pytest.mark.asyncio
async def test_bisect_custom_threshold(client, stores):
    """Bisect respects custom threshold."""
    exec_store, art_store = stores

    await exec_store.create_run(_make_run("good"))
    await exec_store.create_run(_make_run("bad"))

    # Content that is somewhat similar
    await art_store.store(_make_artifact("art-g1", "good", "Hello world"))
    await art_store.store(_make_artifact("art-b1", "bad", "Hello earth"))

    await exec_store.record(
        _make_record("good", "node1", output_refs=["art-g1"]),
    )
    await exec_store.record(
        _make_record("bad", "node1", output_refs=["art-b1"]),
    )

    # Very low threshold should not trigger divergence
    with patch("binex.ui.api.bisect._get_stores", return_value=(exec_store, art_store)):
        resp = await client.post(
            "/api/v1/bisect",
            json={"good_run": "good", "bad_run": "bad", "threshold": 0.1},
        )

    assert resp.status_code == 200
    data = resp.json()
    # With threshold 0.1, similar content should not diverge
    assert data["divergence_node"] is None
