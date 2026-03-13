"""Tests for binex.gateway.registry — AgentRegistry and AgentHealthStatus."""

from __future__ import annotations

import pytest

from binex.gateway.config import AgentEntry, GatewayConfig
from binex.gateway.registry import AgentHealthStatus, AgentRegistry


@pytest.fixture
def sample_agents():
    return [
        AgentEntry(name="r1", endpoint="http://localhost:9001",
                   capabilities=["research", "search"], priority=1),
        AgentEntry(name="r2", endpoint="http://localhost:9002",
                   capabilities=["research"], priority=2),
        AgentEntry(name="s1", endpoint="http://localhost:9003",
                   capabilities=["summarize"], priority=0),
    ]


@pytest.fixture
def registry(sample_agents):
    config = GatewayConfig(agents=sample_agents)
    return AgentRegistry(config)


class TestAgentRegistry:
    def test_find_by_capability(self, registry):
        results = registry.find_by_capability("research")
        assert len(results) == 2
        names = {a.name for a in results}
        assert names == {"r1", "r2"}

    def test_find_by_capability_not_found(self, registry):
        results = registry.find_by_capability("unknown")
        assert results == []

    def test_get_agent(self, registry):
        agent = registry.get_agent("r1")
        assert agent is not None
        assert agent.name == "r1"
        assert agent.endpoint == "http://localhost:9001"

    def test_get_agent_not_found(self, registry):
        assert registry.get_agent("nonexistent") is None

    def test_get_health(self, registry):
        health = registry.get_health("r1")
        assert health is not None
        assert health.status == "alive"
        assert health.consecutive_failures == 0

    def test_get_health_not_found(self, registry):
        assert registry.get_health("nonexistent") is None

    def test_update_health(self, registry):
        registry.update_health("r1", "degraded", latency_ms=5200)
        health = registry.get_health("r1")
        assert health.status == "degraded"
        assert health.last_latency_ms == 5200

    def test_update_health_tracks_failures(self, registry):
        registry.update_health("r1", "down", latency_ms=None)
        h = registry.get_health("r1")
        assert h.consecutive_failures == 1

        registry.update_health("r1", "down", latency_ms=None)
        h = registry.get_health("r1")
        assert h.consecutive_failures == 2

        # Reset on alive
        registry.update_health("r1", "alive", latency_ms=100)
        h = registry.get_health("r1")
        assert h.consecutive_failures == 0

    def test_all_agents(self, registry):
        agents = registry.all_agents()
        assert len(agents) == 3

    def test_empty_registry(self):
        config = GatewayConfig(agents=[])
        reg = AgentRegistry(config)
        assert reg.all_agents() == []
        assert reg.find_by_capability("any") == []


class TestAgentHealthStatus:
    def test_initial_state(self):
        h = AgentHealthStatus(agent_name="test")
        assert h.status == "alive"
        assert h.last_check is None
        assert h.last_latency_ms is None
        assert h.consecutive_failures == 0
