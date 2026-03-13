"""A2A Gateway — FastAPI standalone server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from binex.gateway import Gateway
from binex.gateway.config import GatewayConfig
from binex.gateway.router import RoutingRequest


class _AuthError(Exception):
    """Internal exception raised by auth dependency."""


def create_app(config: GatewayConfig) -> FastAPI:
    """Build and return a FastAPI application wired to a Gateway instance."""

    gateway = Gateway(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await gateway.start()
        try:
            yield
        finally:
            await gateway.stop()

    app = FastAPI(title="Binex A2A Gateway", lifespan=lifespan)

    # ── Auth dependency ─────────────────────────────────────────────

    async def _require_auth(request: Request) -> None:
        """Dependency that enforces auth for protected endpoints."""
        if config.auth is None:
            return
        headers = {k.lower(): v for k, v in request.headers.items()}
        result = await gateway.auth.authenticate(headers)
        if not result.authenticated:
            raise _AuthError()

    # ── Exception handler for auth errors from dependencies ────────

    @app.exception_handler(_AuthError)
    async def auth_error_handler(request: Request, exc: _AuthError):
        return JSONResponse(
            status_code=401,
            content={"error": "Invalid or missing API key"},
        )

    # ── POST /route ─────────────────────────────────────────────────

    @app.post("/route")
    async def route(request: Request) -> JSONResponse:
        body = await request.json()
        routing_request = RoutingRequest(**body)

        # Forward headers to gateway.route() for auth
        headers = {k.lower(): v for k, v in request.headers.items()}

        try:
            result = await gateway.route(routing_request, headers=headers)
        except PermissionError as exc:
            return JSONResponse(
                status_code=401,
                content={"error": str(exc)},
            )
        except ValueError as exc:
            return JSONResponse(
                status_code=404,
                content={"error": str(exc)},
            )
        except RuntimeError as exc:
            return JSONResponse(
                status_code=502,
                content={"error": str(exc)},
            )

        return JSONResponse(
            status_code=200,
            content=result.model_dump(),
        )

    # ── GET /health ─────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> JSONResponse:
        agents_total = 0
        agents_alive = 0
        agents_degraded = 0
        agents_down = 0

        if gateway.registry is not None:
            for agent in gateway.registry.all_agents():
                agents_total += 1
                h = gateway.registry.get_health(agent.name)
                if h is None or h.status == "alive":
                    agents_alive += 1
                elif h.status == "degraded":
                    agents_degraded += 1
                else:
                    agents_down += 1

        overall = "healthy"
        if agents_down == agents_total and agents_total > 0:
            overall = "unhealthy"
        elif agents_down > 0 or agents_degraded > 0:
            overall = "degraded"

        return JSONResponse(
            status_code=200,
            content={
                "status": overall,
                "agents_total": agents_total,
                "agents_alive": agents_alive,
                "agents_degraded": agents_degraded,
                "agents_down": agents_down,
            },
        )

    # ── GET /agents ─────────────────────────────────────────────────

    @app.get("/agents", dependencies=[Depends(_require_auth)])
    async def list_agents() -> JSONResponse:
        agents_out: list[dict[str, Any]] = []
        if gateway.registry is not None:
            for agent in gateway.registry.all_agents():
                h = gateway.registry.get_health(agent.name)
                agents_out.append({
                    "name": agent.name,
                    "endpoint": agent.endpoint,
                    "capabilities": agent.capabilities,
                    "priority": agent.priority,
                    "health": h.status if h else "unknown",
                    "last_latency_ms": h.last_latency_ms if h else None,
                })
        return JSONResponse(status_code=200, content={"agents": agents_out})

    # ── GET /agents/{name} ──────────────────────────────────────────

    @app.get("/agents/{name}", dependencies=[Depends(_require_auth)])
    async def get_agent(name: str) -> JSONResponse:
        if gateway.registry is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Agent '{name}' not found"},
            )
        agent = gateway.registry.get_agent(name)
        if agent is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Agent '{name}' not found"},
            )
        h = gateway.registry.get_health(name)
        return JSONResponse(
            status_code=200,
            content={
                "name": agent.name,
                "endpoint": agent.endpoint,
                "capabilities": agent.capabilities,
                "priority": agent.priority,
                "health": h.status if h else "unknown",
                "last_latency_ms": h.last_latency_ms if h else None,
                "last_check": (
                    h.last_check.isoformat() if h and h.last_check else None
                ),
                "consecutive_failures": (
                    h.consecutive_failures if h else 0
                ),
            },
        )

    # ── POST /agents/refresh ───────────────────────────────────────

    @app.post("/agents/refresh", dependencies=[Depends(_require_auth)])
    async def refresh_agents() -> JSONResponse:
        if gateway.health_checker is not None:
            results = await gateway.health_checker.check_all()
        else:
            results = {}
        return JSONResponse(
            status_code=200,
            content={
                "refreshed": len(results),
                "results": results,
            },
        )

    return app
