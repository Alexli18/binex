"""Tests for the scaffold API endpoints."""

from __future__ import annotations

import httpx
import pytest
import yaml

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
async def test_scaffold_dsl_mode(client):
    """Scaffold from DSL expression generates valid YAML."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "dsl",
        "expression": "A -> B -> C",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == ["A", "B", "C"]
    assert ["A", "B"] in data["edges"]
    assert ["B", "C"] in data["edges"]

    # YAML should be parseable
    workflow = yaml.safe_load(data["yaml"])
    assert "nodes" in workflow
    assert "A" in workflow["nodes"]
    assert "B" in workflow["nodes"]
    assert "C" in workflow["nodes"]


@pytest.mark.asyncio
async def test_scaffold_template_mode(client):
    """Scaffold from a template name returns expected pattern."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "template",
        "template_name": "diamond",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "A" in data["nodes"]
    assert "D" in data["nodes"]
    assert len(data["edges"]) > 0

    workflow = yaml.safe_load(data["yaml"])
    assert "nodes" in workflow


@pytest.mark.asyncio
async def test_scaffold_fan_out(client):
    """Scaffold handles fan-out topology."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "dsl",
        "expression": "planner -> r1, r2, r3",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == ["planner", "r1", "r2", "r3"]
    assert ["planner", "r1"] in data["edges"]
    assert ["planner", "r2"] in data["edges"]
    assert ["planner", "r3"] in data["edges"]


@pytest.mark.asyncio
async def test_scaffold_template_not_found(client):
    """Scaffold returns 404 for unknown template."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "template",
        "template_name": "nonexistent-pattern",
    })

    assert resp.status_code == 404
    assert "Unknown template" in resp.json()["error"]


@pytest.mark.asyncio
async def test_scaffold_missing_expression(client):
    """Scaffold returns 422 when expression is missing in dsl mode."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "dsl",
    })

    assert resp.status_code == 422
    assert "expression is required" in resp.json()["error"]


@pytest.mark.asyncio
async def test_scaffold_missing_template_name(client):
    """Scaffold returns 422 when template_name is missing in template mode."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "template",
    })

    assert resp.status_code == 422
    assert "template_name is required" in resp.json()["error"]


@pytest.mark.asyncio
async def test_scaffold_invalid_mode(client):
    """Scaffold returns 422 for invalid mode."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "invalid",
    })

    assert resp.status_code == 422
    assert "Invalid mode" in resp.json()["error"]


@pytest.mark.asyncio
async def test_scaffold_invalid_dsl(client):
    """Scaffold returns 422 for malformed DSL."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "dsl",
        "expression": "A -> -> B",
    })

    assert resp.status_code == 422
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_scaffold_generated_yaml_has_depends_on(client):
    """Generated YAML includes depends_on for downstream nodes."""
    resp = await client.post("/api/v1/scaffold", json={
        "mode": "dsl",
        "expression": "A -> B -> C",
    })

    assert resp.status_code == 200
    workflow = yaml.safe_load(resp.json()["yaml"])
    assert workflow["nodes"]["B"]["depends_on"] == ["A"]
    assert workflow["nodes"]["C"]["depends_on"] == ["B"]
    # Root node has no depends_on
    assert "depends_on" not in workflow["nodes"]["A"]


@pytest.mark.asyncio
async def test_list_patterns(client):
    """GET /scaffold/patterns returns all known patterns."""
    resp = await client.get("/api/v1/scaffold/patterns")

    assert resp.status_code == 200
    data = resp.json()
    assert "patterns" in data
    assert len(data["patterns"]) > 0

    names = {p["name"] for p in data["patterns"]}
    assert "linear" in names
    assert "diamond" in names
    assert "fan-out" in names

    # Each pattern has expected keys
    for p in data["patterns"]:
        assert "name" in p
        assert "description" in p
        assert "example" in p
