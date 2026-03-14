"""Tests for the cost estimate API endpoint."""

from __future__ import annotations

import httpx
import pytest

from binex.ui.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_estimate_llm_nodes(client):
    yaml_content = """
name: test
nodes:
  summarizer:
    agent: llm://gpt-4o
    config:
      max_tokens: 4000
  classifier:
    agent: llm://gpt-4o-mini
    config:
      max_tokens: 1000
"""
    resp = await client.post("/api/v1/costs/estimate", json={"yaml_content": yaml_content})
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_estimate"] is not None
    assert len(data["nodes"]) == 2

    summarizer = next(n for n in data["nodes"] if n["node_id"] == "summarizer")
    assert summarizer["model"] == "gpt-4o"
    assert summarizer["type"] == "llm"
    assert summarizer["estimated_cost"] == pytest.approx(4000 * 10.0 / 1_000_000)

    classifier = next(n for n in data["nodes"] if n["node_id"] == "classifier")
    assert classifier["estimated_cost"] == pytest.approx(1000 * 0.60 / 1_000_000)


@pytest.mark.asyncio
async def test_estimate_mixed_nodes(client):
    yaml_content = """
name: test
nodes:
  llm_node:
    agent: llm://gpt-4o
  local_node:
    agent: local://my_func
  human_node:
    agent: human://approve
  a2a_node:
    agent: a2a://remote
"""
    resp = await client.post("/api/v1/costs/estimate", json={"yaml_content": yaml_content})
    assert resp.status_code == 200
    data = resp.json()

    nodes = {n["node_id"]: n for n in data["nodes"]}
    assert nodes["local_node"]["estimated_cost"] == 0.0
    assert nodes["human_node"]["estimated_cost"] == 0.0
    assert nodes["a2a_node"]["estimated_cost"] is None
    assert nodes["llm_node"]["estimated_cost"] is not None

    # total_estimate is None because a2a cost is unknown
    assert data["total_estimate"] is None

    # Warnings for a2a
    assert any("a2a" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_estimate_unknown_model(client):
    yaml_content = """
name: test
nodes:
  node1:
    agent: llm://my-custom-model
"""
    resp = await client.post("/api/v1/costs/estimate", json={"yaml_content": yaml_content})
    assert resp.status_code == 200
    data = resp.json()

    assert data["nodes"][0]["estimated_cost"] is None
    assert any("unknown model" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_estimate_invalid_yaml(client):
    resp = await client.post(
        "/api/v1/costs/estimate",
        json={"yaml_content": "{{invalid: yaml: ["},
    )
    assert resp.status_code == 422
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_estimate_no_nodes(client):
    yaml_content = """
name: empty-workflow
"""
    resp = await client.post("/api/v1/costs/estimate", json={"yaml_content": yaml_content})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_estimate"] == 0.0
    assert data["nodes"] == []
    assert any("No nodes" in w for w in data["warnings"])


@pytest.mark.asyncio
async def test_estimate_default_max_tokens(client):
    yaml_content = """
name: test
nodes:
  node1:
    agent: llm://gpt-4o
"""
    resp = await client.post("/api/v1/costs/estimate", json={"yaml_content": yaml_content})
    assert resp.status_code == 200
    data = resp.json()

    node = data["nodes"][0]
    assert node["max_tokens"] == 4096  # default
    assert node["estimated_cost"] == pytest.approx(4096 * 10.0 / 1_000_000)


@pytest.mark.asyncio
async def test_estimate_expensive_warning(client):
    yaml_content = """
name: test
nodes:
  big_node:
    agent: llm://gpt-4o
    config:
      max_tokens: 8000
"""
    resp = await client.post("/api/v1/costs/estimate", json={"yaml_content": yaml_content})
    assert resp.status_code == 200
    data = resp.json()
    assert any("may be expensive" in w for w in data["warnings"])
