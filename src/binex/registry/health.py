"""Health checker for registered agents."""

from __future__ import annotations

import time

import httpx
from pydantic import BaseModel

from binex.models.agent import AgentHealth, AgentInfo


class HealthResult(BaseModel):
    """Result of a single health probe."""

    agent_id: str
    health: AgentHealth
    latency_ms: int
    success: bool
    error: str | None = None


class HealthChecker:
    """Periodically probes agent endpoints and tracks health status."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        latency_slow_ms: int = 2000,
        consecutive_failures_degraded: int = 2,
        consecutive_failures_down: int = 5,
    ) -> None:
        self._client = client
        self.latency_slow_ms = latency_slow_ms
        self.consecutive_failures_degraded = consecutive_failures_degraded
        self.consecutive_failures_down = consecutive_failures_down
        self._consecutive_failures: dict[str, int] = {}

    async def check(self, agent: AgentInfo) -> HealthResult:
        """Probe an agent's health endpoint and return a *HealthResult*."""
        success = False
        error: str | None = None

        t0 = time.monotonic()
        try:
            resp = await self._client.get(
                f"{agent.endpoint}/.well-known/agent.json", timeout=10.0
            )
            resp.raise_for_status()
            success = True
        except (httpx.HTTPStatusError, httpx.HTTPError) as exc:
            error = str(exc)
        t1 = time.monotonic()
        latency_ms = int((t1 - t0) * 1000)

        # Update consecutive failure tracking
        if success:
            self._consecutive_failures[agent.id] = 0
        else:
            self._consecutive_failures[agent.id] = self._consecutive_failures.get(agent.id, 0) + 1

        health = self.compute_health(
            latency_ms=latency_ms,
            success=success,
            consecutive_failures=self._consecutive_failures.get(agent.id, 0),
            latency_slow_ms=self.latency_slow_ms,
            consecutive_failures_degraded=self.consecutive_failures_degraded,
            consecutive_failures_down=self.consecutive_failures_down,
        )

        return HealthResult(
            agent_id=agent.id,
            health=health,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )

    @staticmethod
    def compute_health(
        *,
        latency_ms: int,
        success: bool,
        consecutive_failures: int,
        latency_slow_ms: int = 2000,
        consecutive_failures_degraded: int = 2,
        consecutive_failures_down: int = 5,
    ) -> AgentHealth:
        """Pure function: derive health status from metrics."""
        if not success:
            if consecutive_failures >= consecutive_failures_down:
                return AgentHealth.DOWN
            # Any failure → at minimum DEGRADED
            return AgentHealth.DEGRADED
        if latency_ms > latency_slow_ms:
            return AgentHealth.SLOW
        return AgentHealth.ALIVE


__all__ = ["HealthChecker", "HealthResult"]
