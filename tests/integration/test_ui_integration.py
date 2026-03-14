"""Integration test: full workflow via Web UI API."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.ui.server import create_app


@pytest.fixture
async def stores():
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    run = RunSummary(
        run_id="integ-001",
        workflow_name="test-workflow.yaml",
        workflow_path="examples/test-workflow.yaml",
        status="completed",
        total_nodes=2,
        completed_nodes=2,
        started_at=datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 3, 14, 10, 0, 15, tzinfo=UTC),
        total_cost=0.05,
    )
    await exec_store.create_run(run)

    rec = ExecutionRecord(
        id="rec-1",
        run_id="integ-001",
        task_id="node_a",
        agent_id="llm://gpt-4",
        status="completed",
        latency_ms=150,
        timestamp=datetime(2026, 3, 14, 10, 0, 1, tzinfo=UTC),
        trace_id="trace-1",
    )
    await exec_store.record(rec)

    art = Artifact(
        id="art-1",
        run_id="integ-001",
        type="text",
        content="Hello, integration test!",
        lineage=Lineage(produced_by="node_a"),
    )
    await art_store.store(art)

    cost = CostRecord(
        id="cost-1",
        run_id="integ-001",
        task_id="node_a",
        cost=0.05,
        source="llm_tokens",
        model="gpt-4",
    )
    await exec_store.record_cost(cost)

    return exec_store, art_store


@pytest.fixture
async def client(stores):
    exec_store, art_store = stores

    def mock_stores():
        return exec_store, art_store

    patches = [
        patch("binex.ui.api.runs._get_stores", mock_stores),
        patch("binex.ui.api.artifacts._get_stores", mock_stores),
        patch("binex.ui.api.costs._get_stores", mock_stores),
    ]
    for p in patches:
        p.start()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    for p in patches:
        p.stop()


async def test_full_workflow_via_api(client):
    """Integration: list runs → get run → get artifacts → get costs."""
    # Step 1: List runs
    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 200
    runs = resp.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["run_id"] == "integ-001"
    assert runs[0]["status"] == "completed"

    # Step 2: Get single run
    resp = await client.get("/api/v1/runs/integ-001")
    assert resp.status_code == 200
    run = resp.json()
    assert run["run_id"] == "integ-001"
    assert run["total_cost"] == 0.05

    # Step 3: Get execution records
    resp = await client.get("/api/v1/runs/integ-001/records")
    assert resp.status_code == 200
    records = resp.json()["records"]
    assert len(records) == 1
    assert records[0]["task_id"] == "node_a"

    # Step 4: Get artifacts
    resp = await client.get("/api/v1/runs/integ-001/artifacts")
    assert resp.status_code == 200
    artifacts = resp.json()["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["content"] == "Hello, integration test!"

    # Step 5: Get costs
    resp = await client.get("/api/v1/runs/integ-001/costs")
    assert resp.status_code == 200
    costs = resp.json()
    assert costs["total_cost"] == 0.05
    assert len(costs["records"]) == 1
    assert costs["records"][0]["node_id"] == "node_a"


async def test_run_not_found(client):
    resp = await client.get("/api/v1/runs/nonexistent")
    assert resp.status_code == 404


async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
