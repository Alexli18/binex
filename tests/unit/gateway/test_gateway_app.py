"""Tests for the A2A Gateway FastAPI application."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from binex.gateway.app import create_app
from binex.gateway.config import (
    AgentEntry,
    ApiKeyEntry,
    AuthConfig,
    GatewayConfig,
    HealthConfig,
)
from binex.gateway.router import RoutingResult

# ── Fixtures ────────────────────────────────────────────────────────


def _make_config(*, with_auth: bool = False) -> GatewayConfig:
    """Build a minimal GatewayConfig for testing."""
    agents = [
        AgentEntry(
            name="summarizer",
            endpoint="http://agent1:8000",
            capabilities=["summarize"],
            priority=1,
        ),
        AgentEntry(
            name="translator",
            endpoint="http://agent2:8000",
            capabilities=["translate"],
            priority=2,
        ),
    ]
    auth = None
    if with_auth:
        auth = AuthConfig(
            type="api_key",
            keys=[ApiKeyEntry(name="test-client", key="secret-key-123")],
        )
    return GatewayConfig(
        host="127.0.0.1",
        port=8420,
        auth=auth,
        agents=agents,
        health=HealthConfig(interval_s=60, timeout_ms=3000),
    )


@pytest.fixture()
def config_no_auth() -> GatewayConfig:
    return _make_config(with_auth=False)


@pytest.fixture()
def config_with_auth() -> GatewayConfig:
    return _make_config(with_auth=True)


@pytest.fixture()
def client_no_auth(config_no_auth: GatewayConfig) -> TestClient:
    app = create_app(config_no_auth)
    return TestClient(app)


@pytest.fixture()
def client_with_auth(config_with_auth: GatewayConfig) -> TestClient:
    app = create_app(config_with_auth)
    return TestClient(app)


# ── POST /route ─────────────────────────────────────────────────────


class TestPostRoute:
    """Tests for the POST /route endpoint."""

    def test_route_success(self, client_no_auth: TestClient) -> None:
        """Successful routing returns 200 with RoutingResult."""
        mock_result = RoutingResult(
            artifacts=[{"id": "a1", "content": "done"}],
            cost=0.005,
            routed_to="summarizer",
            endpoint="http://agent1:8000",
            attempts=1,
        )
        with patch(
            "binex.gateway.app.Gateway.route",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client_no_auth.post(
                "/route",
                json={
                    "agent_uri": "a2a://summarize",
                    "task_id": "t1",
                    "skill": "summarize",
                    "trace_id": "tr1",
                    "artifacts": [{"id": "in1", "content": "hello"}],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["routed_to"] == "summarizer"
        assert data["cost"] == 0.005
        assert data["attempts"] == 1
        assert len(data["artifacts"]) == 1

    def test_route_no_agents_404(self, client_no_auth: TestClient) -> None:
        """ValueError from router yields 404."""
        with patch(
            "binex.gateway.app.Gateway.route",
            new_callable=AsyncMock,
            side_effect=ValueError("No agents found for capability 'unknown'"),
        ):
            resp = client_no_auth.post(
                "/route",
                json={
                    "agent_uri": "a2a://unknown",
                    "task_id": "t1",
                    "skill": "unknown",
                    "trace_id": "tr1",
                    "artifacts": [],
                },
            )
        assert resp.status_code == 404
        assert "No agents" in resp.json()["error"]

    def test_route_all_agents_failed_502(
        self, client_no_auth: TestClient,
    ) -> None:
        """RuntimeError from fallback yields 502."""
        with patch(
            "binex.gateway.app.Gateway.route",
            new_callable=AsyncMock,
            side_effect=RuntimeError(
                "All agents failed for 'a2a://summarize'. "
                "summarizer(3 failures)"
            ),
        ):
            resp = client_no_auth.post(
                "/route",
                json={
                    "agent_uri": "a2a://summarize",
                    "task_id": "t1",
                    "skill": "summarize",
                    "trace_id": "tr1",
                    "artifacts": [],
                },
            )
        assert resp.status_code == 502
        assert "All agents failed" in resp.json()["error"]

    def test_route_auth_required_401(
        self, client_with_auth: TestClient,
    ) -> None:
        """POST /route without API key returns 401 when auth is configured."""
        with patch(
            "binex.gateway.app.Gateway.route",
            new_callable=AsyncMock,
            side_effect=PermissionError("Invalid or missing API key"),
        ):
            resp = client_with_auth.post(
                "/route",
                json={
                    "agent_uri": "a2a://summarize",
                    "task_id": "t1",
                    "skill": "summarize",
                    "trace_id": "tr1",
                    "artifacts": [],
                },
            )
        assert resp.status_code == 401
        assert "API key" in resp.json()["error"]

    def test_route_with_valid_api_key(
        self, client_with_auth: TestClient,
    ) -> None:
        """POST /route with valid API key succeeds."""
        mock_result = RoutingResult(
            artifacts=[],
            cost=None,
            routed_to="summarizer",
            endpoint="http://agent1:8000",
            attempts=1,
        )
        with patch(
            "binex.gateway.app.Gateway.route",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            resp = client_with_auth.post(
                "/route",
                json={
                    "agent_uri": "a2a://summarize",
                    "task_id": "t1",
                    "skill": "summarize",
                    "trace_id": "tr1",
                    "artifacts": [],
                },
                headers={"X-API-Key": "secret-key-123"},
            )
        assert resp.status_code == 200

    def test_route_passes_headers_to_gateway(
        self, client_no_auth: TestClient,
    ) -> None:
        """X-API-Key header is forwarded to Gateway.route()."""
        mock_result = RoutingResult(
            artifacts=[],
            cost=None,
            routed_to="summarizer",
            endpoint="http://agent1:8000",
            attempts=1,
        )
        with patch(
            "binex.gateway.app.Gateway.route",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_route:
            client_no_auth.post(
                "/route",
                json={
                    "agent_uri": "a2a://summarize",
                    "task_id": "t1",
                    "skill": "summarize",
                    "trace_id": "tr1",
                    "artifacts": [],
                },
                headers={"X-API-Key": "my-key"},
            )
            call_kwargs = mock_route.call_args
            headers_arg = call_kwargs.kwargs.get("headers", {})
            assert headers_arg.get("x-api-key") == "my-key"


# ── GET /health ─────────────────────────────────────────────────────


class TestGetHealth:
    """Tests for GET /health (no auth required)."""

    def test_health_returns_summary(
        self, client_no_auth: TestClient,
    ) -> None:
        resp = client_no_auth.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["agents_total"] == 2
        assert "agents_alive" in data
        assert "agents_degraded" in data
        assert "agents_down" in data

    def test_health_no_auth_required(
        self, client_with_auth: TestClient,
    ) -> None:
        """GET /health must NOT require authentication."""
        resp = client_with_auth.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


# ── GET /agents ─────────────────────────────────────────────────────


class TestGetAgents:
    """Tests for GET /agents."""

    def test_agents_list(self, client_no_auth: TestClient) -> None:
        resp = client_no_auth.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert len(data["agents"]) == 2
        agent = data["agents"][0]
        assert "name" in agent
        assert "endpoint" in agent
        assert "capabilities" in agent
        assert "priority" in agent
        assert "health" in agent

    def test_agents_auth_required(
        self, client_with_auth: TestClient,
    ) -> None:
        """GET /agents requires auth when configured."""
        resp = client_with_auth.get("/agents")
        assert resp.status_code == 401

    def test_agents_with_valid_key(
        self, client_with_auth: TestClient,
    ) -> None:
        resp = client_with_auth.get(
            "/agents",
            headers={"X-API-Key": "secret-key-123"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["agents"]) == 2


# ── GET /agents/{name} ─────────────────────────────────────────────


class TestGetAgentDetail:
    """Tests for GET /agents/{name}."""

    def test_agent_detail_found(self, client_no_auth: TestClient) -> None:
        resp = client_no_auth.get("/agents/summarizer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "summarizer"
        assert data["endpoint"] == "http://agent1:8000"
        assert "health" in data
        assert "last_check" in data
        assert "consecutive_failures" in data

    def test_agent_detail_not_found(
        self, client_no_auth: TestClient,
    ) -> None:
        resp = client_no_auth.get("/agents/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["error"]

    def test_agent_detail_auth_required(
        self, client_with_auth: TestClient,
    ) -> None:
        resp = client_with_auth.get("/agents/summarizer")
        assert resp.status_code == 401


# ── POST /agents/refresh ───────────────────────────────────────────


class TestPostAgentsRefresh:
    """Tests for POST /agents/refresh."""

    def test_refresh_success(self, client_no_auth: TestClient) -> None:
        with patch(
            "binex.gateway.health.HealthChecker.check_all",
            new_callable=AsyncMock,
            return_value={"summarizer": "alive", "translator": "down"},
        ):
            resp = client_no_auth.post("/agents/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["refreshed"] == 2
        assert data["results"]["summarizer"] == "alive"
        assert data["results"]["translator"] == "down"

    def test_refresh_auth_required(
        self, client_with_auth: TestClient,
    ) -> None:
        resp = client_with_auth.post("/agents/refresh")
        assert resp.status_code == 401

    def test_refresh_with_valid_key(
        self, client_with_auth: TestClient,
    ) -> None:
        with patch(
            "binex.gateway.health.HealthChecker.check_all",
            new_callable=AsyncMock,
            return_value={"summarizer": "alive", "translator": "alive"},
        ):
            resp = client_with_auth.post(
                "/agents/refresh",
                headers={"X-API-Key": "secret-key-123"},
            )
        assert resp.status_code == 200


# ── Lifespan ────────────────────────────────────────────────────────


class TestLifespan:
    """Tests that lifespan starts/stops the gateway."""

    def test_lifespan_calls_start_and_stop(
        self, config_no_auth: GatewayConfig,
    ) -> None:
        with (
            patch(
                "binex.gateway.app.Gateway.start",
                new_callable=AsyncMock,
            ) as mock_start,
            patch(
                "binex.gateway.app.Gateway.stop",
                new_callable=AsyncMock,
            ) as mock_stop,
        ):
            app = create_app(config_no_auth)
            with TestClient(app):
                mock_start.assert_called_once()
            mock_stop.assert_called_once()
