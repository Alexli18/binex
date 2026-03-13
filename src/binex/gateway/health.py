"""Background health checker for registered A2A agents."""

from __future__ import annotations

import asyncio
import time

import httpx

from binex.gateway.config import HealthConfig
from binex.gateway.registry import AgentRegistry


class HealthChecker:
    """Periodically polls registered agents via ``GET /health``.

    Updates the shared :class:`AgentRegistry` with current status and
    latency so the router can make informed decisions.
    """

    def __init__(self, registry: AgentRegistry, config: HealthConfig) -> None:
        self._registry = registry
        self._config = config
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Launch background asyncio task that polls agents."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._check_loop())

    async def stop(self) -> None:
        """Cancel background task and wait for it to finish."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def check_all(self) -> dict[str, str]:
        """Immediate health check for all agents.

        Returns a mapping of ``{agent_name: status}`` where status is
        one of ``"alive"``, ``"degraded"``, or ``"down"``.
        """
        results: dict[str, str] = {}
        timeout = self._config.timeout_ms / 1000.0

        async with httpx.AsyncClient(timeout=timeout) as client:
            for agent in self._registry.all_agents():
                try:
                    start = time.monotonic()
                    response = await client.get(f"{agent.endpoint}/health")
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    response.raise_for_status()

                    status = "alive"
                    self._registry.update_health(
                        agent.name, status, latency_ms=elapsed_ms,
                    )
                    results[agent.name] = status
                except Exception:
                    self._registry.update_health(agent.name, "down")
                    results[agent.name] = "down"

        return results

    async def _check_loop(self) -> None:
        """Background loop: check all agents, then sleep for *interval_s*."""
        while True:
            try:
                await self.check_all()
            except Exception:
                pass  # don't let unexpected errors kill the loop
            await asyncio.sleep(self._config.interval_s)
