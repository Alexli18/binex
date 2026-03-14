"""Tests for the costs API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest

from binex.models.cost import CostRecord
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


def _make_cost_record(
    run_id: str = "run-1",
    task_id: str = "llm_node",
    cost: float = 0.0512,
    model: str = "gpt-4",
    **kwargs,
) -> CostRecord:
    defaults = dict(
        id="cost-1",
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        source="llm_tokens",
        model=model,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    defaults.update(kwargs)
    return CostRecord(**defaults)


@pytest.mark.asyncio
async def test_get_costs(client, stores):
    exec_store, art_store = stores
    await exec_store.record_cost(_make_cost_record("run-1", "llm_node", 0.0512, "gpt-4", id="cost-1"))
    await exec_store.record_cost(
        _make_cost_record("run-1", "summary_node", 0.01, "gpt-3.5-turbo", id="cost-2")
    )

    with patch("binex.ui.api.costs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/costs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["total_cost"] == pytest.approx(0.0612)
    assert len(data["records"]) == 2

    node_ids = {r["node_id"] for r in data["records"]}
    assert node_ids == {"llm_node", "summary_node"}

    rec = next(r for r in data["records"] if r["node_id"] == "llm_node")
    assert rec["run_id"] == "run-1"
    assert rec["cost"] == pytest.approx(0.0512)
    assert rec["model"] == "gpt-4"
    assert rec["source"] == "llm_tokens"


@pytest.mark.asyncio
async def test_get_costs_empty(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.costs._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/costs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert data["total_cost"] == 0.0
    assert data["records"] == []
