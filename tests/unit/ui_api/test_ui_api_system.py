"""Tests for the system API endpoints (doctor, plugins, gateway)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
import respx

from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _check_by_name(checks: list[dict], name: str) -> dict:
    matches = [c for c in checks if c["name"] == name]
    assert matches, f"check {name!r} missing from {[c['name'] for c in checks]}"
    return matches[0]


# ---------------------------------------------------------------------------
# /system/doctor
# ---------------------------------------------------------------------------

# Environment-dependent checks (Artifact Store looks at the local .binex/
# directory) are asserted shape-only — the machine running the suite owes
# the test nothing about its disk. Store connectivity is made
# deterministic by patching get_stores; Python Version is deterministic
# because the suite itself requires 3.11+.


@pytest.mark.asyncio
async def test_doctor_returns_all_checks_with_valid_shape(client):
    stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
    with patch("binex.cli.get_stores", return_value=stores):
        resp = await client.get("/api/v1/system/doctor")

    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert {c["name"] for c in checks} == {
        "Python Version",
        "SQLite Store",
        "Artifact Store",
        "LiteLLM",
    }
    for check in checks:
        assert check["status"] in ("ok", "warn", "error")
        assert check["message"]

    assert _check_by_name(checks, "Python Version")["status"] == "ok"


@pytest.mark.asyncio
async def test_doctor_store_connected(client):
    stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
    with patch("binex.cli.get_stores", return_value=stores):
        resp = await client.get("/api/v1/system/doctor")

    check = _check_by_name(resp.json()["checks"], "SQLite Store")
    assert check["status"] == "ok"
    assert check["message"] == "Connected"


@pytest.mark.asyncio
async def test_doctor_reports_store_failure_without_crashing(client):
    with patch("binex.cli.get_stores", side_effect=RuntimeError("db locked")):
        resp = await client.get("/api/v1/system/doctor")

    assert resp.status_code == 200
    check = _check_by_name(resp.json()["checks"], "SQLite Store")
    assert check["status"] == "error"
    assert "db locked" in check["message"]


# ---------------------------------------------------------------------------
# /system/plugins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plugins_lists_builtin_adapters(client):
    resp = await client.get("/api/v1/system/plugins")

    assert resp.status_code == 200
    plugins = resp.json()["plugins"]
    builtins = {p["name"] for p in plugins if p["builtin"]}
    assert builtins == {"local", "llm", "human", "a2a"}


@pytest.mark.asyncio
async def test_plugins_discovery_failure_is_best_effort(client):
    with patch(
        "binex.plugins.PluginRegistry",
        side_effect=RuntimeError("entry points broken"),
    ):
        resp = await client.get("/api/v1/system/plugins")

    assert resp.status_code == 200
    builtins = {p["name"] for p in resp.json()["plugins"] if p["builtin"]}
    assert builtins == {"local", "llm", "human", "a2a"}


# ---------------------------------------------------------------------------
# /system/gateway
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_gateway_online_reports_agents(client):
    route = respx.get("http://localhost:8421/health").mock(
        return_value=httpx.Response(
            200, json={"agents": [{"name": "researcher"}, {"name": "writer"}]}
        )
    )

    resp = await client.get("/api/v1/system/gateway")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert len(data["agents"]) == 2
    assert data["message"] == "Gateway running, 2 agent(s) registered"
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_gateway_upstream_error_status(client):
    respx.get("http://localhost:8421/health").mock(
        return_value=httpx.Response(500)
    )

    resp = await client.get("/api/v1/system/gateway")

    data = resp.json()
    assert data["status"] == "error"
    assert data["agents"] == []
    assert "500" in data["message"]


@pytest.mark.asyncio
async def test_gateway_offline_returns_structured_response(client):
    # No mocks: point the endpoint at a port nothing listens on and let
    # the connection genuinely fail. A dead dependency must produce a
    # structured "offline" answer, not a 500.
    with patch(
        "binex.ui.api.system._DEFAULT_GATEWAY_URL", "http://127.0.0.1:59999"
    ):
        resp = await client.get("/api/v1/system/gateway")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "offline"
    assert data["agents"] == []
    assert data["message"]
