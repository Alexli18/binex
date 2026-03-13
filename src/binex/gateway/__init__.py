"""A2A Gateway — proxy layer for routing, auth, failover, and health checking."""

from __future__ import annotations

import httpx

from binex.gateway.auth import GatewayAuth, NoAuth, create_auth
from binex.gateway.config import (
    AgentEntry,
    FallbackConfig,
    GatewayConfig,
    load_gateway_config,
)
from binex.gateway.fallback import execute_with_fallback
from binex.gateway.health import HealthChecker
from binex.gateway.registry import AgentRegistry
from binex.gateway.router import Router, RoutingHints, RoutingRequest, RoutingResult


class Gateway:
    """Core gateway that routes A2A requests to remote agents.

    When *config* is ``None`` the gateway operates in pass-through mode:
    explicit URLs are proxied directly without registry lookup.
    """

    def __init__(self, config: GatewayConfig | None) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        if config is not None:
            self._registry = AgentRegistry(config)
            self._router = Router(self._registry)
            self._health_checker: HealthChecker | None = HealthChecker(
                self._registry, config.health,
            )
            self._auth: GatewayAuth = create_auth(config.auth)
        else:
            self._registry = None
            self._router = Router(registry=None)
            self._health_checker = None
            self._auth = NoAuth()

    # ── Public accessors ─────────────────────────────────────────

    @property
    def registry(self) -> AgentRegistry | None:
        return self._registry

    @property
    def auth(self) -> GatewayAuth:
        return self._auth

    @property
    def health_checker(self) -> HealthChecker | None:
        return self._health_checker

    @property
    def config(self) -> GatewayConfig | None:
        return self._config

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Start background services (health checker, HTTP client)."""
        self._client = httpx.AsyncClient()
        if self._health_checker is not None:
            await self._health_checker.start()

    async def stop(self) -> None:
        """Stop background services (health checker, HTTP client)."""
        if self._health_checker is not None:
            await self._health_checker.stop()
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def route(
        self,
        request: RoutingRequest,
        *,
        headers: dict[str, str] | None = None,
    ) -> RoutingResult:
        """Resolve the agent URI and execute the request.

        Returns a ``RoutingResult`` with artifacts, cost, and metadata.
        Raises ``PermissionError`` if authentication fails.
        Raises ``RuntimeError`` if all candidate agents fail.
        """
        # ── Auth gate ────────────────────────────────────────────────
        auth_result = await self._auth.authenticate(headers or {})
        if not auth_result.authenticated:
            raise PermissionError(auth_result.error or "Authentication failed")

        hints = request.routing

        # ── Determine candidate agents ───────────────────────────────
        payload = request.agent_uri
        if payload.startswith("a2a://"):
            payload = payload.removeprefix("a2a://")

        is_explicit = "://" in payload

        if is_explicit:
            # Explicit URL — single candidate, no registry
            agents = [
                AgentEntry(name=payload, endpoint=payload, capabilities=[])
            ]
        else:
            endpoints = self._router.resolve(request.agent_uri, hints=hints)
            # Map endpoints back to AgentEntry objects for fallback
            agents = []
            for ep in endpoints:
                if self._registry is not None:
                    found = False
                    for agent in self._registry.all_agents():
                        if agent.endpoint == ep:
                            agents.append(agent)
                            found = True
                            break
                    if not found:
                        agents.append(
                            AgentEntry(
                                name=ep, endpoint=ep, capabilities=[]
                            )
                        )
                else:
                    agents.append(
                        AgentEntry(name=ep, endpoint=ep, capabilities=[])
                    )

        # ── Resolve fallback config ──────────────────────────────────
        fallback_config = (
            self._config.fallback
            if self._config is not None
            else FallbackConfig()
        )

        # ── Execute with fallback/retry ──────────────────────────────
        # Use shared client if started, otherwise create per-call
        if self._client is not None:
            client = self._client
            result = await execute_with_fallback(
                agents=agents,
                request=request,
                config=fallback_config,
                overrides=hints,
                http_client=client,
            )
        else:
            async with httpx.AsyncClient() as client:
                result = await execute_with_fallback(
                    agents=agents,
                    request=request,
                    config=fallback_config,
                    overrides=hints,
                    http_client=client,
                )

        # Update health on success
        if self._registry is not None:
            self._registry.update_health(result.routed_to, "alive")

        return result


def create_gateway(config_path: str | None = None) -> Gateway:
    """Factory: load config and return a Gateway instance."""
    config = load_gateway_config(config_path)
    return Gateway(config=config)


__all__ = [
    "Gateway",
    "GatewayConfig",
    "RoutingHints",
    "RoutingRequest",
    "RoutingResult",
    "create_gateway",
    "load_gateway_config",
]
