"""Tests for the A2A Gateway HealthChecker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.gateway.config import AgentEntry, GatewayConfig, HealthConfig
from binex.gateway.health import HealthChecker
from binex.gateway.registry import AgentRegistry


def _make_registry(*agents: AgentEntry) -> AgentRegistry:
    config = GatewayConfig(agents=list(agents))
    return AgentRegistry(config)


def _agent(name: str, endpoint: str = "http://localhost:9000") -> AgentEntry:
    return AgentEntry(name=name, endpoint=endpoint, capabilities=["test"])


# ── T019: check_all marks agent alive on successful response ────────


@pytest.mark.asyncio
async def test_check_all_marks_alive_on_success():
    agent = _agent("alpha", "http://alpha:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client):
        result = await checker.check_all()

    assert result["alpha"] == "alive"
    health = registry.get_health("alpha")
    assert health is not None
    assert health.status == "alive"
    assert health.consecutive_failures == 0


# ── T019: check_all marks agent down on connection error ─────────────


@pytest.mark.asyncio
async def test_check_all_marks_down_on_error():
    agent = _agent("beta", "http://beta:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client):
        result = await checker.check_all()

    assert result["beta"] == "down"
    health = registry.get_health("beta")
    assert health is not None
    assert health.status == "down"
    assert health.consecutive_failures == 1


# ── T019: check_all updates latency_ms ───────────────────────────────


@pytest.mark.asyncio
async def test_check_all_updates_latency():
    agent = _agent("gamma", "http://gamma:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client):
        await checker.check_all()

    health = registry.get_health("gamma")
    assert health is not None
    assert health.last_latency_ms is not None
    assert health.last_latency_ms >= 0


# ── T019: start/stop lifecycle ───────────────────────────────────────


@pytest.mark.asyncio
async def test_start_stop_lifecycle():
    agent = _agent("delta", "http://delta:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    assert checker._task is None

    with patch.object(checker, "check_all", new_callable=AsyncMock):
        with patch("binex.gateway.health.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Make sleep raise CancelledError after first call to stop the loop
            mock_sleep.side_effect = asyncio.CancelledError

            await checker.start()
            assert checker._task is not None
            assert not checker._task.done()

            await checker.stop()
            assert checker._task.done() or checker._task.cancelled()


# ── T019: background loop runs at interval ───────────────────────────


@pytest.mark.asyncio
async def test_background_loop_calls_check_all():
    agent = _agent("epsilon", "http://epsilon:8000")
    registry = _make_registry(agent)
    config = HealthConfig(interval_s=10, timeout_ms=5000)
    checker = HealthChecker(registry, config)

    call_count = 0

    async def _mock_check_all():
        nonlocal call_count
        call_count += 1
        return {}

    with patch.object(checker, "check_all", side_effect=_mock_check_all):
        with patch("binex.gateway.health.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Let two iterations run, then cancel
            async def _sleep_side_effect(seconds):
                assert seconds == 10  # should use interval_s
                if call_count >= 2:
                    raise asyncio.CancelledError
            mock_sleep.side_effect = _sleep_side_effect

            await checker.start()

            # Wait for task to finish
            try:
                await checker._task
            except asyncio.CancelledError:
                pass

    assert call_count >= 2


# ── T019: one agent failure doesn't prevent checking others ──────────


@pytest.mark.asyncio
async def test_one_agent_failure_doesnt_block_others():
    agent_a = _agent("agent-ok", "http://ok:8000")
    agent_b = _agent("agent-fail", "http://fail:8000")
    registry = _make_registry(agent_a, agent_b)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    async def _mock_get(url, **kwargs):
        if "fail" in url:
            raise httpx.ConnectError("connection refused")
        return mock_response

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=_mock_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client):
        result = await checker.check_all()

    assert result["agent-ok"] == "alive"
    assert result["agent-fail"] == "down"

    health_ok = registry.get_health("agent-ok")
    health_fail = registry.get_health("agent-fail")
    assert health_ok.status == "alive"
    assert health_fail.status == "down"


# ── T019: check_all marks down on HTTP error status ──────────────────


@pytest.mark.asyncio
async def test_check_all_marks_down_on_http_error():
    agent = _agent("zeta", "http://zeta:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=mock_response)
    )

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client):
        result = await checker.check_all()

    assert result["zeta"] == "down"


# ── T020: Gateway start/stop integration ─────────────────────────────


@pytest.mark.asyncio
async def test_gateway_creates_health_checker_with_config():
    from binex.gateway import Gateway

    config = GatewayConfig(
        agents=[_agent("svc", "http://svc:8000")],
        health=HealthConfig(interval_s=15, timeout_ms=3000),
    )
    gw = Gateway(config)
    assert gw._health_checker is not None


@pytest.mark.asyncio
async def test_gateway_no_health_checker_without_config():
    from binex.gateway import Gateway

    gw = Gateway(None)
    assert gw._health_checker is None


@pytest.mark.asyncio
async def test_gateway_start_stop():
    from binex.gateway import Gateway

    config = GatewayConfig(
        agents=[_agent("svc", "http://svc:8000")],
        health=HealthConfig(interval_s=15, timeout_ms=3000),
    )
    gw = Gateway(config)

    with patch.object(gw._health_checker, "start", new_callable=AsyncMock) as mock_start:
        with patch.object(gw._health_checker, "stop", new_callable=AsyncMock) as mock_stop:
            await gw.start()
            mock_start.assert_awaited_once()

            await gw.stop()
            mock_stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_gateway_start_stop_no_config():
    from binex.gateway import Gateway

    gw = Gateway(None)
    # Should not raise
    await gw.start()
    await gw.stop()


# ── T019: consecutive failures increment ─────────────────────────────


@pytest.mark.asyncio
async def test_consecutive_failures_increment():
    agent = _agent("eta", "http://eta:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client):
        await checker.check_all()
        assert registry.get_health("eta").consecutive_failures == 1
        await checker.check_all()
        assert registry.get_health("eta").consecutive_failures == 2


# ── T019: successful check resets consecutive failures ───────────────


@pytest.mark.asyncio
async def test_success_resets_consecutive_failures():
    agent = _agent("theta", "http://theta:8000")
    registry = _make_registry(agent)
    checker = HealthChecker(registry, HealthConfig(interval_s=30, timeout_ms=5000))

    # First: fail
    mock_client_fail = AsyncMock(spec=httpx.AsyncClient)
    mock_client_fail.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    mock_client_fail.__aenter__ = AsyncMock(return_value=mock_client_fail)
    mock_client_fail.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client_fail):
        await checker.check_all()
    assert registry.get_health("theta").consecutive_failures == 1

    # Then: succeed
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    mock_client_ok = AsyncMock(spec=httpx.AsyncClient)
    mock_client_ok.get = AsyncMock(return_value=mock_response)
    mock_client_ok.__aenter__ = AsyncMock(return_value=mock_client_ok)
    mock_client_ok.__aexit__ = AsyncMock(return_value=False)

    with patch("binex.gateway.health.httpx.AsyncClient", return_value=mock_client_ok):
        await checker.check_all()
    assert registry.get_health("theta").consecutive_failures == 0
