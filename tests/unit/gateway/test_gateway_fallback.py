"""Tests for gateway fallback/retry layer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from binex.gateway.config import (
    AgentEntry,
    ApiKeyEntry,
    AuthConfig,
    FallbackConfig,
    GatewayConfig,
)
from binex.gateway.fallback import execute_with_fallback
from binex.gateway.router import RoutingHints, RoutingRequest

# ── Helpers ──────────────────────────────────────────────────────────


def _make_agent(name: str, endpoint: str) -> AgentEntry:
    return AgentEntry(name=name, endpoint=endpoint, capabilities=["cap"])


def _make_request(uri: str = "a2a://cap") -> RoutingRequest:
    return RoutingRequest(
        agent_uri=uri,
        task_id="t1",
        skill="cap",
        trace_id="tr1",
        artifacts=[{"id": "a1", "type": "text", "content": "hello"}],
    )


def _ok_response() -> httpx.Response:
    """Build a successful httpx.Response."""
    req = httpx.Request("POST", "http://mock/execute")
    return httpx.Response(
        200,
        json={"artifacts": [{"type": "text", "content": "ok"}], "cost": 0.01},
        request=req,
    )


def _error_response(status: int = 500) -> httpx.Response:
    req = httpx.Request("POST", "http://mock/execute")
    return httpx.Response(status, request=req)


# ── Tests ────────────────────────────────────────────────────────────


class TestExecuteWithFallbackSuccess:
    """T1: execute_with_fallback success on first try."""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        agents = [_make_agent("a", "http://a:9000")]
        config = FallbackConfig(retry_count=2, failover=True)
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _ok_response()

        result = await execute_with_fallback(
            agents=agents,
            request=request,
            config=config,
            overrides=None,
            http_client=client,
        )

        assert result.routed_to == "a"
        assert result.endpoint == "http://a:9000"
        assert result.attempts == 1
        assert result.artifacts == [{"type": "text", "content": "ok"}]
        assert result.cost == 0.01
        client.post.assert_called_once()


class TestRetryFixedBackoff:
    """T2: Retry with fixed backoff (mock asyncio.sleep to verify delays)."""

    @pytest.mark.asyncio
    async def test_retry_fixed_backoff(self):
        agents = [_make_agent("a", "http://a:9000")]
        config = FallbackConfig(
            retry_count=3,
            retry_backoff="fixed",
            retry_base_delay_ms=200,
            failover=False,
        )
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        # Fail twice, succeed on third retry (attempt index 2)
        client.post.side_effect = [
            httpx.ConnectError("fail1"),
            httpx.ConnectError("fail2"),
            _ok_response(),
        ]

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await execute_with_fallback(
                agents=agents,
                request=request,
                config=config,
                overrides=None,
                http_client=client,
            )

        assert result.routed_to == "a"
        assert result.attempts == 3
        # Fixed backoff: constant delay 0.2s each time
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.2)


class TestRetryExponentialBackoff:
    """T3: Retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        agents = [_make_agent("a", "http://a:9000")]
        config = FallbackConfig(
            retry_count=3,
            retry_backoff="exponential",
            retry_base_delay_ms=500,
            failover=False,
        )
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = [
            httpx.ConnectError("fail1"),
            httpx.ConnectError("fail2"),
            _ok_response(),
        ]

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await execute_with_fallback(
                agents=agents,
                request=request,
                config=config,
                overrides=None,
                http_client=client,
            )

        assert result.routed_to == "a"
        assert result.attempts == 3
        # Exponential: 0.5 * 2^0 = 0.5, 0.5 * 2^1 = 1.0
        assert mock_sleep.call_count == 2
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls[0] == 0.5
        assert calls[1] == 1.0


class TestFailoverToNextAgent:
    """T4: Failover to next agent after retries exhausted."""

    @pytest.mark.asyncio
    async def test_failover_to_next_agent(self):
        agents = [
            _make_agent("primary", "http://primary:9000"),
            _make_agent("secondary", "http://secondary:9000"),
        ]
        config = FallbackConfig(
            retry_count=1,
            retry_backoff="fixed",
            retry_base_delay_ms=100,
            failover=True,
        )
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        # Primary: initial + 1 retry = 2 failures
        # Secondary: success on first try
        client.post.side_effect = [
            httpx.ConnectError("primary-fail-1"),
            httpx.ConnectError("primary-fail-2"),
            _ok_response(),
        ]

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            result = await execute_with_fallback(
                agents=agents,
                request=request,
                config=config,
                overrides=None,
                http_client=client,
            )

        assert result.routed_to == "secondary"
        assert result.endpoint == "http://secondary:9000"
        # 2 attempts on primary + 1 on secondary = 3
        assert result.attempts == 3


class TestFailoverDisabled:
    """T5: Failover disabled — stops after first agent retries."""

    @pytest.mark.asyncio
    async def test_failover_disabled_stops_after_first_agent(self):
        agents = [
            _make_agent("primary", "http://primary:9000"),
            _make_agent("secondary", "http://secondary:9000"),
        ]
        config = FallbackConfig(
            retry_count=1,
            retry_backoff="fixed",
            retry_base_delay_ms=100,
            failover=False,
        )
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("always-fail")

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="All agents failed"):
                await execute_with_fallback(
                    agents=agents,
                    request=request,
                    config=config,
                    overrides=None,
                    http_client=client,
                )

        # Only 2 calls: initial + 1 retry for first agent, no second agent
        assert client.post.call_count == 2


class TestAllCandidatesFail:
    """T6: All candidates fail → RuntimeError with attempts info."""

    @pytest.mark.asyncio
    async def test_all_candidates_fail_raises_runtime_error(self):
        agents = [
            _make_agent("a", "http://a:9000"),
            _make_agent("b", "http://b:9000"),
        ]
        config = FallbackConfig(
            retry_count=1,
            retry_backoff="fixed",
            retry_base_delay_ms=100,
            failover=True,
        )
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("always-fail")

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="All agents failed") as exc_info:
                await execute_with_fallback(
                    agents=agents,
                    request=request,
                    config=config,
                    overrides=None,
                    http_client=client,
                )

        error_msg = str(exc_info.value)
        assert "a" in error_msg
        assert "b" in error_msg
        # 2 agents * 2 attempts each = 4
        assert client.post.call_count == 4


class TestPerRequestOverrides:
    """T7: Per-request overrides (retry_count from hints)."""

    @pytest.mark.asyncio
    async def test_override_retry_count(self):
        agents = [_make_agent("a", "http://a:9000")]
        config = FallbackConfig(
            retry_count=5,
            retry_backoff="fixed",
            retry_base_delay_ms=100,
            failover=False,
        )
        request = _make_request()
        overrides = RoutingHints(retry_count=1, failover=False)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("fail")

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await execute_with_fallback(
                    agents=agents,
                    request=request,
                    config=config,
                    overrides=overrides,
                    http_client=client,
                )

        # Override retry_count=1: initial + 1 retry = 2
        assert client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_override_failover(self):
        """Override failover=False even when config says True."""
        agents = [
            _make_agent("a", "http://a:9000"),
            _make_agent("b", "http://b:9000"),
        ]
        config = FallbackConfig(
            retry_count=0,
            failover=True,
        )
        request = _make_request()
        overrides = RoutingHints(failover=False)

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("fail")

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await execute_with_fallback(
                    agents=agents,
                    request=request,
                    config=config,
                    overrides=overrides,
                    http_client=client,
                )

        # No failover: only 1 call (retry_count=0, no failover)
        assert client.post.call_count == 1


class TestSingleAgentExplicitUrl:
    """T8: Single agent (explicit URL) — retry only, no failover."""

    @pytest.mark.asyncio
    async def test_single_explicit_agent_retries(self):
        agents = [_make_agent("http://explicit:9000", "http://explicit:9000")]
        config = FallbackConfig(
            retry_count=2,
            retry_backoff="exponential",
            retry_base_delay_ms=100,
            failover=True,  # irrelevant — only one agent
        )
        request = _make_request("a2a://http://explicit:9000")

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = [
            httpx.ConnectError("fail1"),
            _ok_response(),
        ]

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await execute_with_fallback(
                agents=agents,
                request=request,
                config=config,
                overrides=None,
                http_client=client,
            )

        assert result.routed_to == "http://explicit:9000"
        assert result.attempts == 2
        assert mock_sleep.call_count == 1


class TestRetryWithHttpStatusError:
    """Verify retries also trigger on HTTP status errors (e.g. 500)."""

    @pytest.mark.asyncio
    async def test_retry_on_http_500(self):
        agents = [_make_agent("a", "http://a:9000")]
        config = FallbackConfig(retry_count=2, retry_backoff="fixed", retry_base_delay_ms=100)
        request = _make_request()

        error_resp = _error_response(500)
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = [
            httpx.HTTPStatusError("500", request=error_resp.request, response=error_resp),
            _ok_response(),
        ]

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            result = await execute_with_fallback(
                agents=agents,
                request=request,
                config=config,
                overrides=None,
                http_client=client,
            )

        assert result.attempts == 2


class TestZeroRetryCount:
    """When retry_count=0, no retries — fail immediately."""

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        agents = [_make_agent("a", "http://a:9000")]
        config = FallbackConfig(retry_count=0, failover=False)
        request = _make_request()

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.side_effect = httpx.ConnectError("fail")

        with patch("binex.gateway.fallback.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await execute_with_fallback(
                    agents=agents,
                    request=request,
                    config=config,
                    overrides=None,
                    http_client=client,
                )

        assert client.post.call_count == 1


# ── Shared httpx mock fixture ────────────────────────────────────────


class _HttpxMock:
    def __init__(self):
        self._responses: list[dict] = []

    def add_response(
        self,
        *,
        url: str,
        json: dict | None = None,
        status_code: int = 200,
    ):
        self._responses.append(
            {"url": url, "json": json or {}, "status_code": status_code}
        )

    def _find_response(self, url: str) -> dict | None:
        for i, r in enumerate(self._responses):
            if r["url"] == url:
                return self._responses.pop(i)
        return None


class _MockResponse:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "http://mock")
            resp = httpx.Response(
                self.status_code, request=req
            )
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=req,
                response=resp,
            )


@pytest.fixture
def httpx_mock():
    """Lightweight httpx mock for gateway integration tests."""
    mock = _HttpxMock()

    class _MockAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, *, json=None, timeout=None):
            resp = mock._find_response(url)
            if resp is None:
                raise httpx.ConnectError(f"No mock for {url}")
            return _MockResponse(resp["status_code"], resp["json"])

    with patch(
        "httpx.AsyncClient", return_value=_MockAsyncClient()
    ):
        yield mock


# ── Gateway integration tests ───────────────────────────────────────


class TestGatewayFallbackIntegration:
    """Gateway.route() uses execute_with_fallback."""

    @pytest.mark.asyncio
    async def test_gateway_route_uses_fallback(self, httpx_mock):
        from binex.gateway import Gateway

        config = GatewayConfig(
            agents=[
                AgentEntry(
                    name="agent-a",
                    endpoint="http://a:9000",
                    capabilities=["summarize"],
                    priority=1,
                ),
            ],
            fallback=FallbackConfig(retry_count=2, failover=True),
        )

        httpx_mock.add_response(
            url="http://a:9000/execute",
            json={"artifacts": [{"type": "text", "content": "done"}]},
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://summarize",
            task_id="t1",
            skill="summarize",
            trace_id="tr1",
            artifacts=[],
        )
        result = await gw.route(req)
        assert result.routed_to == "agent-a"

    @pytest.mark.asyncio
    async def test_gateway_route_explicit_url_with_fallback(self, httpx_mock):
        from binex.gateway import Gateway

        httpx_mock.add_response(
            url="http://explicit:9000/execute",
            json={"artifacts": []},
        )

        gw = Gateway(config=None)
        req = RoutingRequest(
            agent_uri="a2a://http://explicit:9000",
            task_id="t1",
            skill="x",
            trace_id="tr1",
            artifacts=[],
        )
        result = await gw.route(req)
        assert result.endpoint == "http://explicit:9000"


# ── Gateway auth integration tests ──────────────────────────────────


class TestGatewayAuthIntegration:
    """Gateway.route() integrates auth from T013."""

    @pytest.mark.asyncio
    async def test_auth_pass_allows_routing(self, httpx_mock):
        from binex.gateway import Gateway

        config = GatewayConfig(
            agents=[
                AgentEntry(
                    name="a",
                    endpoint="http://a:9000",
                    capabilities=["cap"],
                ),
            ],
            auth=AuthConfig(
                type="api_key",
                keys=[ApiKeyEntry(name="client1", key="secret123")],
            ),
            fallback=FallbackConfig(retry_count=0),
        )

        httpx_mock.add_response(
            url="http://a:9000/execute",
            json={"artifacts": []},
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://cap",
            task_id="t1",
            skill="cap",
            trace_id="tr1",
            artifacts=[],
        )
        result = await gw.route(req, headers={"X-API-Key": "secret123"})
        assert result.routed_to == "a"

    @pytest.mark.asyncio
    async def test_auth_fail_raises_permission_error(self):
        from binex.gateway import Gateway

        config = GatewayConfig(
            agents=[
                AgentEntry(
                    name="a",
                    endpoint="http://a:9000",
                    capabilities=["cap"],
                ),
            ],
            auth=AuthConfig(
                type="api_key",
                keys=[ApiKeyEntry(name="client1", key="secret123")],
            ),
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://cap",
            task_id="t1",
            skill="cap",
            trace_id="tr1",
            artifacts=[],
        )
        with pytest.raises(PermissionError, match="Invalid or missing API key"):
            await gw.route(req, headers={"X-API-Key": "wrong-key"})

    @pytest.mark.asyncio
    async def test_no_auth_config_allows_all(self, httpx_mock):
        """When auth config is None, NoAuth allows all requests."""
        from binex.gateway import Gateway

        httpx_mock.add_response(
            url="http://a:9000/execute",
            json={"artifacts": []},
        )

        config = GatewayConfig(
            agents=[
                AgentEntry(name="a", endpoint="http://a:9000", capabilities=["cap"]),
            ],
            fallback=FallbackConfig(retry_count=0),
        )

        gw = Gateway(config=config)
        req = RoutingRequest(
            agent_uri="a2a://cap",
            task_id="t1",
            skill="cap",
            trace_id="tr1",
            artifacts=[],
        )
        # No headers needed — NoAuth allows all
        result = await gw.route(req)
        assert result.routed_to == "a"

    @pytest.mark.asyncio
    async def test_route_without_headers_param_backwards_compat(self, httpx_mock):
        """Existing code that calls route(request) without headers still works."""
        from binex.gateway import Gateway

        httpx_mock.add_response(
            url="http://x:9000/execute",
            json={"artifacts": []},
        )

        gw = Gateway(config=None)
        req = RoutingRequest(
            agent_uri="a2a://http://x:9000",
            task_id="t1",
            skill="x",
            trace_id="tr1",
            artifacts=[],
        )
        result = await gw.route(req)
        assert result.endpoint == "http://x:9000"
