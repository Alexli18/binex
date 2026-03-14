"""Tests for the artifacts API endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from binex.models.artifact import Artifact, Lineage
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.ui.server import create_app


@pytest.fixture
def stores():
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    return exec_store, art_store


@pytest.fixture
def app(stores):
    with patch("binex.ui.api.artifacts._get_stores", return_value=stores):
        yield create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_artifacts(client, stores):
    _, art_store = stores
    artifact = Artifact(
        id="art-1",
        run_id="run-1",
        type="text",
        content="Hello, world!",
        lineage=Lineage(produced_by="node_a"),
    )
    await art_store.store(artifact)

    resp = await client.get("/api/v1/runs/run-1/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["artifacts"]) == 1
    art = data["artifacts"][0]
    assert art["type"] == "text"
    assert art["content"] == "Hello, world!"
    assert art["lineage"]["produced_by"] == "node_a"
    assert art["lineage"]["step"] == 0
    assert art["lineage"]["derived_from"] is None


@pytest.mark.asyncio
async def test_get_artifacts_empty(client):
    resp = await client.get("/api/v1/runs/run-999/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifacts"] == []
