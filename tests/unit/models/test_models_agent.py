"""Tests for AgentInfo and AgentHealth models."""

from datetime import UTC, datetime

from binex.models.agent import AgentHealth, AgentInfo


class TestAgentHealth:
    def test_values(self) -> None:
        assert AgentHealth.ALIVE == "alive"
        assert AgentHealth.SLOW == "slow"
        assert AgentHealth.DEGRADED == "degraded"
        assert AgentHealth.DOWN == "down"


class TestAgentInfo:
    def test_create_minimal(self) -> None:
        ai = AgentInfo(id="agent_01", endpoint="http://localhost:9001", name="Planner")
        assert ai.capabilities == []
        assert ai.health == AgentHealth.ALIVE
        assert ai.latency_avg_ms == 0
        assert isinstance(ai.last_seen, datetime)
        assert ai.agent_card == {}

    def test_create_full(self) -> None:
        ai = AgentInfo(
            id="agent_02",
            endpoint="http://localhost:9002",
            name="Researcher",
            capabilities=["research.search", "research.summarize"],
            health=AgentHealth.SLOW,
            latency_avg_ms=500,
            agent_card={"version": "1.0"},
        )
        assert len(ai.capabilities) == 2
        assert ai.health == AgentHealth.SLOW
        assert ai.latency_avg_ms == 500

    def test_last_seen_utc(self) -> None:
        ai = AgentInfo(id="a", endpoint="http://x", name="X")
        assert ai.last_seen.tzinfo == UTC
