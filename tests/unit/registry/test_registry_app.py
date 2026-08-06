"""Tests for the agent registry FastAPI app."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from binex.models.agent import AgentHealth
from binex.registry.app import app, registry_state


@pytest.fixture(autouse=True)
def _clear_registry():
    registry_state.agents.clear()
    yield
    registry_state.agents.clear()


def _register_agent(client: TestClient, **overrides) -> dict:
    payload = {
        "endpoint": "http://localhost:9001",
        "name": "Planner",
        "capabilities": ["plan"],
    }
    payload.update(overrides)
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def client():
    return TestClient(app)


# --- GET /health ---


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- POST /agents ---


def test_register_agent(client: TestClient) -> None:
    data = _register_agent(client)
    assert "id" in data
    assert data["name"] == "Planner"
    assert data["endpoint"] == "http://localhost:9001"
    assert data["capabilities"] == ["plan"]
    assert data["health"] == "alive"


def test_register_agent_auto_generates_id(client: TestClient) -> None:
    data = _register_agent(client)
    assert data["id"]
    assert len(data["id"]) > 0


def test_register_agent_with_explicit_id(client: TestClient) -> None:
    data = _register_agent(client, id="my-agent-1")
    assert data["id"] == "my-agent-1"


def test_register_agent_stored(client: TestClient) -> None:
    data = _register_agent(client)
    assert data["id"] in registry_state.agents


# --- GET /agents ---


def test_list_agents_empty(client: TestClient) -> None:
    resp = client.get("/agents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_agents(client: TestClient) -> None:
    _register_agent(client, name="A")
    _register_agent(client, name="B")
    resp = client.get("/agents")
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 2


def test_list_agents_filter_by_capability(client: TestClient) -> None:
    _register_agent(client, name="A", capabilities=["plan"])
    _register_agent(client, name="B", capabilities=["research"])
    resp = client.get("/agents", params={"capability": "research"})
    agents = resp.json()
    assert len(agents) == 1
    assert agents[0]["name"] == "B"


def test_list_agents_filter_by_health(client: TestClient) -> None:
    a = _register_agent(client, name="A")
    _register_agent(client, name="B")
    # Manually set health to DOWN for first agent
    registry_state.agents[a["id"]].health = AgentHealth.DOWN
    resp = client.get("/agents", params={"health": "alive"})
    agents = resp.json()
    assert len(agents) == 1
    assert agents[0]["name"] == "B"


def test_list_agents_filter_by_capability_and_health(client: TestClient) -> None:
    a = _register_agent(client, name="A", capabilities=["plan"])
    _register_agent(client, name="B", capabilities=["plan"])
    registry_state.agents[a["id"]].health = AgentHealth.DOWN
    resp = client.get("/agents", params={"capability": "plan", "health": "alive"})
    agents = resp.json()
    assert len(agents) == 1
    assert agents[0]["name"] == "B"


# --- GET /agents/{id} ---


def test_get_agent(client: TestClient) -> None:
    data = _register_agent(client)
    resp = client.get(f"/agents/{data['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == data["id"]


def test_get_agent_not_found(client: TestClient) -> None:
    resp = client.get("/agents/nonexistent")
    assert resp.status_code == 404


# --- DELETE /agents/{id} ---


def test_delete_agent(client: TestClient) -> None:
    data = _register_agent(client)
    resp = client.delete(f"/agents/{data['id']}")
    assert resp.status_code == 204
    assert data["id"] not in registry_state.agents


def test_delete_agent_not_found(client: TestClient) -> None:
    resp = client.delete("/agents/nonexistent")
    assert resp.status_code == 404


# --- GET /agents/search ---


def test_search_by_capability(client: TestClient) -> None:
    _register_agent(client, name="A", capabilities=["plan", "research"])
    _register_agent(client, name="B", capabilities=["research"])
    _register_agent(client, name="C", capabilities=["code"])
    resp = client.get("/agents/search", params={"capability": "research"})
    assert resp.status_code == 200
    agents = resp.json()
    assert len(agents) == 2
    names = {a["name"] for a in agents}
    assert names == {"A", "B"}


def test_search_no_match(client: TestClient) -> None:
    _register_agent(client, name="A", capabilities=["plan"])
    resp = client.get("/agents/search", params={"capability": "unknown"})
    assert resp.status_code == 200
    assert resp.json() == []
