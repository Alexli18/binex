"""QA v5 gap tests for A2A Gateway — config, auth, registry, health, router, fallback."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from binex.gateway.auth import ApiKeyAuth, NoAuth
from binex.gateway.config import (
    AgentEntry,
    ApiKeyEntry,
    FallbackConfig,
    GatewayConfig,
    HealthConfig,
    _interpolate_env,
    _interpolate_recursive,
    load_gateway_config,
)
from binex.gateway.health import HealthChecker
from binex.gateway.registry import AgentRegistry
from binex.gateway.router import Router, RoutingHints, RoutingRequest

# ═══════════════════════════════════════════════════════════════════════
# CAT-1: Config Validation
# ═══════════════════════════════════════════════════════════════════════


class TestConfigGaps:
    """TC-CFG-001 through TC-CFG-008."""

    def test_cfg_001_multiple_env_vars_in_single_value(self, monkeypatch):
        """Multiple ${VAR} references in one string are all interpolated."""
        monkeypatch.setenv("GW_HOST", "example.com")
        monkeypatch.setenv("GW_PORT", "9999")
        result = _interpolate_env("http://${GW_HOST}:${GW_PORT}/api")
        assert result == "http://example.com:9999/api"

    def test_cfg_002_whitespace_only_api_key_rejected(self):
        """Whitespace-only API key triggers validator."""
        with pytest.raises(ValueError, match="must not be empty"):
            ApiKeyEntry(name="test", key="   ")

    def test_cfg_003_empty_yaml_loads_default_config(self, tmp_path):
        """Empty YAML file returns GatewayConfig with defaults."""
        config_file = tmp_path / "gateway.yaml"
        config_file.write_text("")
        result = load_gateway_config(str(config_file))
        assert result is not None
        assert isinstance(result, GatewayConfig)
        assert result.port == 8420
        assert result.host == "0.0.0.0"

    def test_cfg_004_fallback_retry_count_zero_boundary(self):
        """retry_count=0 is valid (no retries, only initial attempt)."""
        fc = FallbackConfig(retry_count=0)
        assert fc.retry_count == 0

    def test_cfg_005_health_config_boundary_minimums(self):
        """interval_s=1 and timeout_ms=1 are valid boundary minimums."""
        hc = HealthConfig(interval_s=1, timeout_ms=1)
        assert hc.interval_s == 1
        assert hc.timeout_ms == 1

    def test_cfg_006_interpolate_recursive_non_string_passthrough(self):
        """int, float, bool, None pass through _interpolate_recursive unchanged."""
        assert _interpolate_recursive(42) == 42
        assert _interpolate_recursive(3.14) == 3.14
        assert _interpolate_recursive(True) is True
        assert _interpolate_recursive(None) is None

    def test_cfg_007_config_search_fallback_to_cwd_gateway_yaml(self, tmp_path, monkeypatch):
        """When .binex/gateway.yaml absent, ./gateway.yaml is found."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "gateway.yaml"
        config_file.write_text(yaml.dump({"port": 9999}))
        result = load_gateway_config(None)
        assert result is not None
        assert result.port == 9999

    def test_cfg_008_invalid_backoff_literal_rejected(self):
        """Invalid retry_backoff value rejected by pydantic Literal."""
        with pytest.raises(Exception):
            FallbackConfig(retry_backoff="linear")


# ═══════════════════════════════════════════════════════════════════════
# CAT-2: Auth Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestAuthGaps:
    """TC-AUTH-001 through TC-AUTH-003."""

    @pytest.mark.asyncio
    async def test_auth_001_duplicate_keys_last_writer_wins(self):
        """Two ApiKeyEntry with same key value — last name overwrites."""
        keys = [
            ApiKeyEntry(name="client-a", key="shared-key"),
            ApiKeyEntry(name="client-b", key="shared-key"),
        ]
        auth = ApiKeyAuth(keys)
        result = await auth.authenticate({"X-API-Key": "shared-key"})
        assert result.authenticated
        assert result.client_name == "client-b"

    @pytest.mark.asyncio
    async def test_auth_002_whitespace_in_api_key_not_trimmed(self):
        """API key with trailing space does not match key without it."""
        keys = [ApiKeyEntry(name="c", key="mykey")]
        auth = ApiKeyAuth(keys)
        result = await auth.authenticate({"X-API-Key": "mykey "})
        assert not result.authenticated

    @pytest.mark.asyncio
    async def test_auth_003_noauth_returns_none_client_name(self):
        """NoAuth always returns client_name=None."""
        auth = NoAuth()
        result = await auth.authenticate({})
        assert result.authenticated
        assert result.client_name is None


# ═══════════════════════════════════════════════════════════════════════
# CAT-3: Registry Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestRegistryGaps:
    """TC-REG-001 through TC-REG-003."""

    def _make_registry(self, agents=None):
        if agents is None:
            agents = [
                AgentEntry(
                    name="agent-a",
                    endpoint="http://a:8000",
                    capabilities=["translate", "summarize"],
                    priority=0,
                ),
            ]
        config = GatewayConfig(agents=agents)
        return AgentRegistry(config)

    def test_reg_001_update_health_unknown_agent_noop(self):
        """update_health with nonexistent name does nothing (no error)."""
        reg = self._make_registry()
        reg.update_health("nonexistent", "down", latency_ms=100)
        assert reg.get_health("nonexistent") is None

    def test_reg_002_degraded_increments_consecutive_failures(self):
        """Degraded status increments consecutive_failures like down."""
        reg = self._make_registry()
        reg.update_health("agent-a", "degraded")
        h = reg.get_health("agent-a")
        assert h.consecutive_failures == 1
        assert h.status == "degraded"

        reg.update_health("agent-a", "degraded")
        h = reg.get_health("agent-a")
        assert h.consecutive_failures == 2

    def test_reg_003_multi_capability_agent_found_by_any(self):
        """Agent with multiple capabilities found by any of them."""
        reg = self._make_registry()
        assert len(reg.find_by_capability("translate")) == 1
        assert len(reg.find_by_capability("summarize")) == 1
        assert len(reg.find_by_capability("unknown-cap")) == 0


# ═══════════════════════════════════════════════════════════════════════
# CAT-4: Health Checker Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestHealthCheckerGaps:
    """TC-HC-001 through TC-HC-004."""

    def _make_checker(self, agents=None):
        if agents is None:
            agents = []
        config = GatewayConfig(agents=agents)
        registry = AgentRegistry(config)
        hc_config = HealthConfig(interval_s=1, timeout_ms=1000)
        return HealthChecker(registry, hc_config), registry

    @pytest.mark.asyncio
    async def test_hc_001_start_twice_idempotent(self):
        """Calling start() twice does not create a second task."""
        checker, _ = self._make_checker()
        await checker.start()
        task1 = checker._task
        await checker.start()
        task2 = checker._task
        assert task1 is task2
        await checker.stop()

    @pytest.mark.asyncio
    async def test_hc_002_stop_when_no_task(self):
        """stop() with _task=None does nothing (no error)."""
        checker, _ = self._make_checker()
        assert checker._task is None
        await checker.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_hc_003_check_loop_survives_exception(self):
        """_check_loop catches exceptions from check_all and continues."""
        checker, _ = self._make_checker()
        call_count = 0

        original_check_all = checker.check_all

        async def failing_check_all():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("simulated failure")
            return await original_check_all()

        checker.check_all = failing_check_all
        checker._config.interval_s = 0  # immediate loop for speed
        await checker.start()
        await asyncio.sleep(0.1)
        await checker.stop()
        assert call_count >= 2, "Loop should survive the exception and call again"

    @pytest.mark.asyncio
    async def test_hc_004_check_all_empty_registry(self):
        """check_all with no agents returns empty dict."""
        checker, _ = self._make_checker(agents=[])
        results = await checker.check_all()
        assert results == {}


# ═══════════════════════════════════════════════════════════════════════
# CAT-5: Router Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestRouterGaps:
    """TC-RTR-001 through TC-RTR-002."""

    def _make_router_with_agents(self, agents):
        config = GatewayConfig(agents=agents)
        registry = AgentRegistry(config)
        return Router(registry), registry

    def test_rtr_001_health_none_latency_fallback(self):
        """Agent with health=None gets 999999 latency in sort key."""
        agents = [
            AgentEntry(name="a", endpoint="http://a:8000", capabilities=["cap"], priority=0),
            AgentEntry(name="b", endpoint="http://b:8000", capabilities=["cap"], priority=0),
        ]
        router, registry = self._make_router_with_agents(agents)
        # Update b with latency, leave a at default (None latency but alive status)
        registry.update_health("b", "alive", latency_ms=50)
        # a has None latency → should sort after b (999999 > 50)
        endpoints = router.resolve("cap")
        assert endpoints[0] == "http://b:8000"
        assert endpoints[1] == "http://a:8000"

    def test_rtr_002_degraded_none_vs_measured_latency(self):
        """Degraded agent with None latency sorts after one with measured latency."""
        agents = [
            AgentEntry(name="a", endpoint="http://a:8000", capabilities=["cap"], priority=0),
            AgentEntry(name="b", endpoint="http://b:8000", capabilities=["cap"], priority=0),
        ]
        router, registry = self._make_router_with_agents(agents)
        registry.update_health("a", "degraded")  # None latency → 999999
        registry.update_health("b", "degraded", latency_ms=100)
        endpoints = router.resolve("cap")
        assert endpoints[0] == "http://b:8000"
        assert endpoints[1] == "http://a:8000"


# ═══════════════════════════════════════════════════════════════════════
# CAT-6: Fallback Edge Cases
# ═══════════════════════════════════════════════════════════════════════


class TestFallbackGaps:
    """TC-FB-001 through TC-FB-004."""

    @pytest.mark.asyncio
    async def test_fb_001_no_artifacts_key_defaults_empty(self):
        """Response without 'artifacts' key returns empty list."""
        from binex.gateway.fallback import execute_with_fallback

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"cost": 0.5}  # no "artifacts"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        agent = AgentEntry(name="a", endpoint="http://a:8000", capabilities=[])
        request = RoutingRequest(
            agent_uri="a2a://http://a:8000", task_id="t1", trace_id="tr1",
        )
        result = await execute_with_fallback(
            agents=[agent], request=request,
            config=FallbackConfig(), overrides=None,
            http_client=mock_client,
        )
        assert result.artifacts == []
        assert result.cost == 0.5

    @pytest.mark.asyncio
    async def test_fb_002_no_cost_key_defaults_none(self):
        """Response without 'cost' key returns cost=None."""
        from binex.gateway.fallback import execute_with_fallback

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"artifacts": [{"id": "1"}]}  # no "cost"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        agent = AgentEntry(name="a", endpoint="http://a:8000", capabilities=[])
        request = RoutingRequest(
            agent_uri="a2a://http://a:8000", task_id="t1", trace_id="tr1",
        )
        result = await execute_with_fallback(
            agents=[agent], request=request,
            config=FallbackConfig(), overrides=None,
            http_client=mock_client,
        )
        assert result.cost is None
        assert result.artifacts == [{"id": "1"}]

    @pytest.mark.asyncio
    async def test_fb_003_timeout_override_from_routing_hints(self):
        """timeout_ms from RoutingHints overrides default 30s."""
        from binex.gateway.fallback import execute_with_fallback

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"artifacts": []}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        agent = AgentEntry(name="a", endpoint="http://a:8000", capabilities=[])
        request = RoutingRequest(
            agent_uri="a2a://http://a:8000", task_id="t1", trace_id="tr1",
        )
        overrides = RoutingHints(timeout_ms=5000)
        await execute_with_fallback(
            agents=[agent], request=request,
            config=FallbackConfig(), overrides=overrides,
            http_client=mock_client,
        )
        # Verify timeout was passed as 5.0 seconds
        call_kwargs = mock_client.post.call_args
        assert call_kwargs.kwargs.get("timeout") == 5.0

    @pytest.mark.asyncio
    async def test_fb_004_empty_agents_raises_runtime_error(self):
        """Empty agents list raises RuntimeError immediately."""
        from binex.gateway.fallback import execute_with_fallback

        mock_client = AsyncMock()
        request = RoutingRequest(
            agent_uri="a2a://cap", task_id="t1", trace_id="tr1",
        )
        with pytest.raises(RuntimeError, match="All agents failed"):
            await execute_with_fallback(
                agents=[], request=request,
                config=FallbackConfig(), overrides=None,
                http_client=mock_client,
            )
