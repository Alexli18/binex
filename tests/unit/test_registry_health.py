"""Tests for the registry health checker module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.models.agent import AgentHealth, AgentInfo
from binex.registry.health import HealthChecker, HealthResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent(
    agent_id: str = "agent-1", endpoint: str = "http://agent.example.com"
) -> AgentInfo:
    return AgentInfo(id=agent_id, endpoint=endpoint, name="Test Agent")


def _mock_response(*, status_code: int = 200, json_data: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def checker(client: AsyncMock) -> HealthChecker:
    return HealthChecker(client=client, latency_slow_ms=2000)


# ---------------------------------------------------------------------------
# compute_health – pure logic
# ---------------------------------------------------------------------------


class TestComputeHealth:
    """Test the pure compute_health method covering all status transitions."""

    def test_success_normal_latency_returns_alive(self) -> None:
        result = HealthChecker.compute_health(latency_ms=100, success=True, consecutive_failures=0)
        assert result is AgentHealth.ALIVE

    def test_success_high_latency_returns_slow(self) -> None:
        result = HealthChecker.compute_health(
            latency_ms=3000, success=True, consecutive_failures=0, latency_slow_ms=2000
        )
        assert result is AgentHealth.SLOW

    def test_failure_below_degraded_threshold_returns_degraded(self) -> None:
        # Even 1 failure without reaching the degraded threshold still returns DEGRADED
        # because any failure is at minimum DEGRADED-candidate; but per spec,
        # consecutive_failures >= consecutive_failures_degraded (default 2).
        # With 1 failure, below threshold → still not degraded. Let's check the boundary.
        result = HealthChecker.compute_health(
            latency_ms=0,
            success=False,
            consecutive_failures=1,
            consecutive_failures_degraded=2,
            consecutive_failures_down=5,
        )
        # 1 failure < 2 threshold → not yet degraded, but still a failure.
        # The spec says: if not success and >= degraded → DEGRADED, if >= down → DOWN.
        # Below degraded threshold with failure → still mark DEGRADED (minimum failure state).
        assert result is AgentHealth.DEGRADED

    def test_failure_at_degraded_threshold_returns_degraded(self) -> None:
        result = HealthChecker.compute_health(
            latency_ms=0,
            success=False,
            consecutive_failures=2,
            consecutive_failures_degraded=2,
            consecutive_failures_down=5,
        )
        assert result is AgentHealth.DEGRADED

    def test_failure_at_down_threshold_returns_down(self) -> None:
        result = HealthChecker.compute_health(
            latency_ms=0,
            success=False,
            consecutive_failures=5,
            consecutive_failures_degraded=2,
            consecutive_failures_down=5,
        )
        assert result is AgentHealth.DOWN

    def test_failure_above_down_threshold_returns_down(self) -> None:
        result = HealthChecker.compute_health(
            latency_ms=0,
            success=False,
            consecutive_failures=10,
            consecutive_failures_degraded=2,
            consecutive_failures_down=5,
        )
        assert result is AgentHealth.DOWN


# ---------------------------------------------------------------------------
# check() – async integration with mocked httpx
# ---------------------------------------------------------------------------


class TestHealthCheck:
    """Test the async check() method with mocked HTTP responses."""

    async def test_successful_check_returns_alive(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        client.get.return_value = _mock_response(status_code=200)

        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.1]  # 100ms
            result = await checker.check(_make_agent())

        assert result.success is True
        assert result.health is AgentHealth.ALIVE
        assert result.latency_ms == 100
        assert result.error is None
        client.get.assert_called_once_with(
            "http://agent.example.com/.well-known/agent.json", timeout=10.0
        )

    async def test_slow_response_returns_slow(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        client.get.return_value = _mock_response(status_code=200)

        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 3.0]  # 3000ms
            result = await checker.check(_make_agent())

        assert result.success is True
        assert result.health is AgentHealth.SLOW
        assert result.latency_ms == 3000

    async def test_consecutive_failures_transition_to_degraded(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        client.get.return_value = _mock_response(status_code=500)
        agent = _make_agent()

        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.05, 0.0, 0.05]
            r1 = await checker.check(agent)
            r2 = await checker.check(agent)

        # After 2 consecutive failures (== consecutive_failures_degraded default 2)
        assert r1.success is False
        assert r2.success is False
        assert r2.health is AgentHealth.DEGRADED

    async def test_more_consecutive_failures_transition_to_down(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        client.get.return_value = _mock_response(status_code=500)
        agent = _make_agent()

        with patch("binex.registry.health.time") as mock_time:
            # 5 failures, each pair: [start, end]
            mock_time.monotonic.side_effect = [0.0, 0.01] * 5
            results = []
            for _ in range(5):
                results.append(await checker.check(agent))

        assert results[-1].health is AgentHealth.DOWN

    async def test_recovery_from_down_to_alive(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        agent = _make_agent()

        # First: 5 failures to reach DOWN
        client.get.return_value = _mock_response(status_code=500)
        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.01] * 5
            for _ in range(5):
                await checker.check(agent)

        # Then: 1 success → should recover to ALIVE
        client.get.return_value = _mock_response(status_code=200)
        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.05]
            result = await checker.check(agent)

        assert result.success is True
        assert result.health is AgentHealth.ALIVE

    async def test_network_error_counts_as_failure(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        client.get.side_effect = httpx.ConnectError("connection refused")
        agent = _make_agent()

        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.01]
            result = await checker.check(agent)

        assert result.success is False
        assert result.error is not None
        assert "connection refused" in result.error

    async def test_network_error_repeated_reaches_degraded(
        self, checker: HealthChecker, client: AsyncMock
    ) -> None:
        client.get.side_effect = httpx.ConnectError("connection refused")
        agent = _make_agent()

        with patch("binex.registry.health.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.01] * 2
            await checker.check(agent)
            result = await checker.check(agent)

        assert result.health is AgentHealth.DEGRADED


# ---------------------------------------------------------------------------
# HealthResult model
# ---------------------------------------------------------------------------


class TestHealthResult:
    def test_health_result_fields(self) -> None:
        hr = HealthResult(
            agent_id="a1",
            health=AgentHealth.ALIVE,
            latency_ms=42,
            success=True,
        )
        assert hr.agent_id == "a1"
        assert hr.health is AgentHealth.ALIVE
        assert hr.latency_ms == 42
        assert hr.success is True
        assert hr.error is None

    def test_health_result_with_error(self) -> None:
        hr = HealthResult(
            agent_id="a1",
            health=AgentHealth.DOWN,
            latency_ms=0,
            success=False,
            error="timeout",
        )
        assert hr.error == "timeout"
