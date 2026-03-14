"""Tests for the lineage API endpoint."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from binex.models.artifact import Artifact, Lineage
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


def _make_artifact(
    run_id: str = "run-1",
    art_id: str = "art-1",
    produced_by: str = "node_a",
    art_type: str = "text",
    content: str = "hello",
    derived_from: list[str] | None = None,
) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


@pytest.mark.asyncio
async def test_lineage_basic(client, stores):
    exec_store, art_store = stores
    await art_store.store(_make_artifact(art_id="art-1", produced_by="node_a"))
    await art_store.store(
        _make_artifact(art_id="art-2", produced_by="node_b", derived_from=["art-1"]),
    )

    with patch("binex.ui.api.lineage._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/lineage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == "run-1"
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1

    edge = data["edges"][0]
    assert edge["source"] == "art-1"
    assert edge["target"] == "art-2"

    node_ids = {n["id"] for n in data["nodes"]}
    assert node_ids == {"art-1", "art-2"}

    art2_node = next(n for n in data["nodes"] if n["id"] == "art-2")
    assert art2_node["produced_by"] == "node_b"
    assert art2_node["type"] == "text"


@pytest.mark.asyncio
async def test_lineage_no_artifacts(client, stores):
    exec_store, art_store = stores

    with patch("binex.ui.api.lineage._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/lineage")

    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []


@pytest.mark.asyncio
async def test_lineage_chain(client, stores):
    """Three artifacts in a chain: A -> B -> C."""
    exec_store, art_store = stores
    await art_store.store(_make_artifact(art_id="a", produced_by="n1"))
    await art_store.store(_make_artifact(art_id="b", produced_by="n2", derived_from=["a"]))
    await art_store.store(_make_artifact(art_id="c", produced_by="n3", derived_from=["b"]))

    with patch("binex.ui.api.lineage._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/lineage")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2

    edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
    assert ("a", "b") in edge_pairs
    assert ("b", "c") in edge_pairs


@pytest.mark.asyncio
async def test_lineage_multiple_parents(client, stores):
    """Artifact derived from multiple parents."""
    exec_store, art_store = stores
    await art_store.store(_make_artifact(art_id="p1", produced_by="n1"))
    await art_store.store(_make_artifact(art_id="p2", produced_by="n2"))
    await art_store.store(
        _make_artifact(art_id="child", produced_by="n3", derived_from=["p1", "p2"]),
    )

    with patch("binex.ui.api.lineage._get_stores", return_value=(exec_store, art_store)):
        resp = await client.get("/api/v1/runs/run-1/lineage")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2

    edge_pairs = {(e["source"], e["target"]) for e in data["edges"]}
    assert ("p1", "child") in edge_pairs
    assert ("p2", "child") in edge_pairs
