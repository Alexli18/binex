"""Tests for the cost dashboard API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import httpx
import pytest

from binex.models.cost import CostRecord
from binex.models.execution import RunSummary
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


def _make_run(run_id: str, started_at: datetime | None = None) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-wf",
        status="completed",
        total_nodes=2,
        completed_nodes=2,
        started_at=started_at or datetime.now(UTC),
    )


def _make_cost(
    run_id: str,
    task_id: str,
    cost: float,
    model: str,
    record_id: str = "c1",
    timestamp: datetime | None = None,
) -> CostRecord:
    return CostRecord(
        id=record_id,
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        source="llm_tokens",
        model=model,
        timestamp=timestamp or datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_dashboard_empty(client, stores):
    exec_store, art_store = stores
    with patch("binex.ui.api.cost_dashboard._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/costs/dashboard")

    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "7d"
    assert data["total_cost"] == 0.0
    assert data["run_count"] == 0
    assert data["avg_per_run"] == 0.0
    assert data["cost_by_model"] == []
    assert data["cost_by_node"] == []
    assert data["cost_trend"] == []


@pytest.mark.asyncio
async def test_dashboard_with_data(client, stores):
    exec_store, art_store = stores
    now = datetime.now(UTC)

    await exec_store.create_run(_make_run("r1", started_at=now - timedelta(hours=1)))
    await exec_store.create_run(_make_run("r2", started_at=now - timedelta(hours=2)))

    await exec_store.record_cost(_make_cost("r1", "node_a", 0.10, "gpt-4o", "c1", now))
    await exec_store.record_cost(_make_cost("r1", "node_b", 0.05, "gpt-4o-mini", "c2", now))
    await exec_store.record_cost(_make_cost("r2", "node_a", 0.20, "gpt-4o", "c3", now))

    with patch("binex.ui.api.cost_dashboard._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/costs/dashboard?period=7d")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_count"] == 2
    assert data["total_cost"] == pytest.approx(0.35)
    assert data["avg_per_run"] == pytest.approx(0.175)

    # cost_by_model sorted by cost desc
    models = {m["model"]: m for m in data["cost_by_model"]}
    assert "gpt-4o" in models
    assert models["gpt-4o"]["cost"] == pytest.approx(0.30)
    assert models["gpt-4o"]["count"] == 2

    # cost_by_node
    nodes = {n["node_id"]: n for n in data["cost_by_node"]}
    assert "node_a" in nodes
    assert nodes["node_a"]["cost"] == pytest.approx(0.30)
    assert nodes["node_a"]["count"] == 2

    # cost_trend
    assert len(data["cost_trend"]) >= 1


@pytest.mark.asyncio
async def test_dashboard_period_filter(client, stores):
    exec_store, art_store = stores
    now = datetime.now(UTC)

    # One recent, one old
    await exec_store.create_run(_make_run("r1", started_at=now - timedelta(hours=1)))
    await exec_store.create_run(_make_run("r2", started_at=now - timedelta(days=10)))

    await exec_store.record_cost(_make_cost("r1", "n", 0.10, "gpt-4o", "c1", now))
    await exec_store.record_cost(
        _make_cost("r2", "n", 0.50, "gpt-4o", "c2", now - timedelta(days=10))
    )

    with patch("binex.ui.api.cost_dashboard._get_stores", return_value=(exec_store, art_store)):
        resp_7d = await client.get("/api/v1/costs/dashboard?period=7d")
        resp_all = await client.get("/api/v1/costs/dashboard?period=all")

    data_7d = resp_7d.json()
    assert data_7d["run_count"] == 1
    assert data_7d["total_cost"] == pytest.approx(0.10)

    data_all = resp_all.json()
    assert data_all["run_count"] == 2
    assert data_all["total_cost"] == pytest.approx(0.60)


@pytest.mark.asyncio
async def test_dashboard_invalid_period(client, stores):
    exec_store, art_store = stores
    with patch("binex.ui.api.cost_dashboard._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/costs/dashboard?period=invalid")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_dashboard_24h_period(client, stores):
    exec_store, art_store = stores
    now = datetime.now(UTC)

    await exec_store.create_run(_make_run("r1", started_at=now - timedelta(hours=12)))
    await exec_store.create_run(_make_run("r2", started_at=now - timedelta(days=2)))

    await exec_store.record_cost(_make_cost("r1", "n", 0.10, "gpt-4o", "c1", now))

    with patch("binex.ui.api.cost_dashboard._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/costs/dashboard?period=24h")

    data = resp.json()
    assert data["run_count"] == 1
    assert data["period"] == "24h"
