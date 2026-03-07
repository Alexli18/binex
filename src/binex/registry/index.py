"""Capability index and search for the agent registry."""

from __future__ import annotations

from binex.models.agent import AgentHealth, AgentInfo

_HEALTH_RANK: dict[AgentHealth, int] = {
    AgentHealth.ALIVE: 0,
    AgentHealth.SLOW: 1,
    AgentHealth.DEGRADED: 2,
    AgentHealth.DOWN: 3,
}


class CapabilityIndex:
    """Reverse index mapping capabilities to agent IDs with ranked search."""

    def __init__(self, store: dict[str, AgentInfo]) -> None:
        self._store = store
        self._index: dict[str, set[str]] = {}

    def add_agent(self, agent: AgentInfo) -> None:
        """Index all capabilities of an agent."""
        for cap in agent.capabilities:
            self._index.setdefault(cap, set()).add(agent.id)

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent from all capability indexes."""
        empty_caps: list[str] = []
        for cap, ids in self._index.items():
            ids.discard(agent_id)
            if not ids:
                empty_caps.append(cap)
        for cap in empty_caps:
            del self._index[cap]

    def update_agent(self, agent: AgentInfo) -> None:
        """Re-index an agent (remove old entries, add new ones)."""
        self.remove_agent(agent.id)
        self.add_agent(agent)

    def search(self, capability: str) -> list[AgentInfo]:
        """Return agents matching a capability, ranked by health then latency."""
        agent_ids = self._index.get(capability, set())
        agents = [self._store[aid] for aid in agent_ids if aid in self._store]
        return self._rank(agents)

    def search_multi(self, capabilities: list[str]) -> list[AgentInfo]:
        """Return agents matching ALL specified capabilities, ranked."""
        if not capabilities:
            return []
        sets = [self._index.get(cap, set()) for cap in capabilities]
        common_ids = sets[0].intersection(*sets[1:])
        agents = [self._store[aid] for aid in common_ids if aid in self._store]
        return self._rank(agents)

    @staticmethod
    def _rank(agents: list[AgentInfo]) -> list[AgentInfo]:
        return sorted(agents, key=lambda a: (_HEALTH_RANK.get(a.health, 99), a.latency_avg_ms))


__all__ = ["CapabilityIndex"]
