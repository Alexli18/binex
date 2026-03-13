"""In-memory agent registry with health tracking."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from binex.gateway.config import AgentEntry, GatewayConfig


class AgentHealthStatus(BaseModel):
    """Runtime health state for a registered agent."""

    agent_name: str
    status: str = "alive"  # alive | degraded | down
    last_check: datetime | None = None
    last_latency_ms: int | None = None
    consecutive_failures: int = 0


class AgentRegistry:
    """In-memory agent registry loaded from GatewayConfig."""

    def __init__(self, config: GatewayConfig) -> None:
        self._agents: dict[str, AgentEntry] = {
            a.name: a for a in config.agents
        }
        self._health: dict[str, AgentHealthStatus] = {
            a.name: AgentHealthStatus(agent_name=a.name)
            for a in config.agents
        }

    def find_by_capability(self, capability: str) -> list[AgentEntry]:
        """Return agents that declare the given capability."""
        return [
            a for a in self._agents.values()
            if capability in a.capabilities
        ]

    def get_agent(self, name: str) -> AgentEntry | None:
        """Lookup a single agent by name."""
        return self._agents.get(name)

    def get_health(self, name: str) -> AgentHealthStatus | None:
        """Get current health status for an agent."""
        return self._health.get(name)

    def update_health(
        self,
        name: str,
        status: str,
        *,
        latency_ms: int | None = None,
    ) -> None:
        """Update agent health status."""
        health = self._health.get(name)
        if health is None:
            return
        health.status = status
        health.last_check = datetime.now()
        health.last_latency_ms = latency_ms
        if status in ("down", "degraded"):
            health.consecutive_failures += 1
        else:
            health.consecutive_failures = 0

    def all_agents(self) -> list[AgentEntry]:
        """Return all registered agents."""
        return list(self._agents.values())
