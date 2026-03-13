"""Gateway router — resolves agent URIs to endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from binex.gateway.registry import AgentRegistry


class RoutingHints(BaseModel):
    """Per-request routing preferences."""

    prefer: str = "highest_priority"
    timeout_ms: int | None = None
    retry_count: int | None = None
    failover: bool | None = None


class RoutingRequest(BaseModel):
    """Incoming routing request."""

    agent_uri: str
    task_id: str
    skill: str | None = None
    trace_id: str
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    routing: RoutingHints | None = None


class RoutingResult(BaseModel):
    """Result of a routed request."""

    artifacts: list[dict[str, Any]]
    cost: float | None = None
    routed_to: str
    endpoint: str
    attempts: int


class Router:
    """Resolves agent URIs to ordered endpoint lists.

    Dual-mode parsing:
      - If payload after ``a2a://`` contains ``://`` → explicit URL passthrough
      - Otherwise → capability lookup via registry
    """

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self._registry = registry

    def resolve(
        self,
        agent_uri: str,
        *,
        hints: RoutingHints | None = None,
    ) -> list[str]:
        """Return ordered list of endpoint URLs for the given URI.

        Raises ``ValueError`` if capability lookup finds no healthy agents.
        """
        # Strip a2a:// prefix if present
        payload = agent_uri
        if payload.startswith("a2a://"):
            payload = payload.removeprefix("a2a://")

        # Explicit URL passthrough — payload itself contains ://
        if "://" in payload:
            return [payload]

        # Capability lookup via registry
        if self._registry is None:
            raise ValueError(
                f"No agents found for capability '{payload}' "
                f"(no registry configured)"
            )

        candidates = self._registry.find_by_capability(payload)
        if not candidates:
            raise ValueError(
                f"No agents found for capability '{payload}'"
            )

        # Filter: only alive or degraded agents
        healthy = []
        for agent in candidates:
            health = self._registry.get_health(agent.name)
            if health is None or health.status in ("alive", "degraded"):
                healthy.append(agent)

        if not healthy:
            raise ValueError(
                f"No agents found for capability '{payload}' "
                f"(all agents are down)"
            )

        # Sort: health (alive > degraded) → priority (lower first) → latency
        def _sort_key(agent):
            health = self._registry.get_health(agent.name)
            status_order = 0 if (health is None or health.status == "alive") else 1
            has_latency = health and health.last_latency_ms is not None
            latency = health.last_latency_ms if has_latency else 999999
            return (status_order, agent.priority, latency)

        healthy.sort(key=_sort_key)
        return [a.endpoint for a in healthy]
