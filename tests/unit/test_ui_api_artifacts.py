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


_PNG = b"\x89PNG\r\n\x1a\n" + b"pixels" * 10


@pytest.fixture
def bin_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))
    return InMemoryExecutionStore(), InMemoryArtifactStore()


@pytest.fixture
def bin_app(bin_stores):
    with patch("binex.ui.api.artifacts._get_stores", return_value=bin_stores):
        yield create_app()


@pytest.fixture
async def bin_client(bin_app):
    transport = ASGITransport(app=bin_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_binary_artifact_flagged_and_blob_served(bin_client, bin_stores):
    from binex.artifacts.binary import make_binary_artifact
    _, art_store = bin_stores
    art = make_binary_artifact("run-b", "gen", _PNG, "image/png")
    await art_store.store(art)

    listing = await bin_client.get("/api/v1/runs/run-b/artifacts")
    item = listing.json()["artifacts"][0]
    assert item["binary"] is True
    assert item["mime"] == "image/png"
    assert item["blob_url"] == f"/api/v1/runs/run-b/artifacts/{art.id}/blob"
    # content stays the envelope, never raw bytes
    assert item["content"]["kind"] == "binary"

    blob = await bin_client.get(item["blob_url"])
    assert blob.status_code == 200
    assert blob.headers["content-type"] == "image/png"
    assert blob.content == _PNG


@pytest.mark.asyncio
async def test_blob_404_for_unknown_artifact(bin_client):
    resp = await bin_client.get("/api/v1/runs/run-b/artifacts/nope/blob")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_blob_400_for_non_binary(bin_client, bin_stores):
    _, art_store = bin_stores
    await art_store.store(Artifact(
        id="json-1", run_id="run-b", type="result", content={"x": 1},
        lineage=Lineage(produced_by="n"),
    ))
    resp = await bin_client.get("/api/v1/runs/run-b/artifacts/json-1/blob")
    assert resp.status_code == 400
