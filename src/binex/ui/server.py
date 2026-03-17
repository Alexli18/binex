"""FastAPI app factory for Binex Web UI."""

from __future__ import annotations

import pathlib
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from binex.ui.api.artifacts import router as artifacts_router
from binex.ui.api.bisect import router as bisect_router
from binex.ui.api.cost_dashboard import router as cost_dashboard_router
from binex.ui.api.costs import router as costs_router
from binex.ui.api.debug import router as debug_router
from binex.ui.api.diagnose import router as diagnose_router
from binex.ui.api.diff import router as diff_router
from binex.ui.api.errors import APIError
from binex.ui.api.estimate import router as estimate_router
from binex.ui.api.events import router as events_router
from binex.ui.api.export import router as export_router
from binex.ui.api.gateway import router as gateway_router
from binex.ui.api.lineage import router as lineage_router
from binex.ui.api.prompt_templates import router as prompt_templates_router
from binex.ui.api.prompts import router as prompts_router
from binex.ui.api.providers import router as providers_router

# replay endpoint is now in runs.py (POST /runs/replay)
from binex.ui.api.runs import router as runs_router
from binex.ui.api.scaffold import router as scaffold_router
from binex.ui.api.scheduler import router as scheduler_router
from binex.ui.api.system import router as system_router
from binex.ui.api.tools import router as tools_router
from binex.ui.api.trace import router as trace_router
from binex.ui.api.workflows import router as workflows_router

STATIC_DIR = pathlib.Path(__file__).parent / "static"

# Module-level start time for uptime calculation
_START_TIME: float = 0.0


def _get_version() -> str:
    """Return the installed binex package version."""
    try:
        from binex import __version__
        return __version__
    except Exception:
        return "unknown"


def create_app(*, dev: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Parameters
    ----------
    dev:
        When ``True`` the app runs in development mode: CORS is enabled for
        ``localhost:5173`` (Vite dev server) and error responses include
        full detail.  When ``False`` (default / production) the pre-built
        React app is served from ``STATIC_DIR``.
    """
    global _START_TIME  # noqa: PLW0603
    _START_TIME = time.monotonic()

    app = FastAPI(title="Binex Web UI", version=_get_version())

    # Store mode flag on app state so endpoints can read it
    app.state.dev_mode = dev  # type: ignore[attr-defined]

    # --- CORS (dev mode only) ---
    if dev:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Global APIError handler ---
    @app.exception_handler(APIError)
    async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_response_body(),
        )

    # --- Routers ---
    app.include_router(artifacts_router, prefix="/api/v1")
    app.include_router(bisect_router, prefix="/api/v1")
    app.include_router(cost_dashboard_router, prefix="/api/v1")
    app.include_router(costs_router, prefix="/api/v1")
    app.include_router(debug_router, prefix="/api/v1")
    app.include_router(diagnose_router, prefix="/api/v1")
    app.include_router(diff_router, prefix="/api/v1")
    app.include_router(estimate_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(export_router, prefix="/api/v1")
    app.include_router(gateway_router, prefix="/api/v1")
    app.include_router(lineage_router, prefix="/api/v1")
    app.include_router(prompt_templates_router, prefix="/api/v1")
    app.include_router(prompts_router, prefix="/api/v1")
    app.include_router(providers_router, prefix="/api/v1")
    # replay_router removed — endpoint now in runs_router
    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(scheduler_router, prefix="/api/v1")
    app.include_router(scaffold_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(system_router, prefix="/api/v1")
    app.include_router(trace_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")

    # --- Enhanced health endpoint ---
    @app.get("/api/v1/health")
    async def health() -> JSONResponse:
        uptime_s = round(time.monotonic() - _START_TIME, 1)
        version = _get_version()

        # Check frontend static build
        has_frontend = (STATIC_DIR / "index.html").is_file()

        # Check SQLite connectivity
        store_ok = False
        store_message = "not checked"
        try:
            from binex.cli import get_stores
            exec_store, _ = get_stores()
            await exec_store.close()
            store_ok = True
            store_message = "connected"
        except Exception as exc:
            store_message = str(exc)

        return JSONResponse({
            "status": "ok",
            "version": version,
            "uptime_s": uptime_s,
            "frontend_built": has_frontend,
            "store": {"ok": store_ok, "message": store_message},
        })

    # --- Config endpoint ---
    @app.get("/api/v1/config")
    async def config() -> JSONResponse:
        return JSONResponse({
            "mode": "dev" if dev else "prod",
            "version": _get_version(),
        })

    # Mount static files and SPA fallback only if the static directory exists
    if (STATIC_DIR / "index.html").is_file():
        # SPA fallback: serve index.html for any GET request that doesn't match /api/*
        @app.get("/{full_path:path}")
        async def spa_fallback(request: Request, full_path: str) -> FileResponse:
            # Try to serve the exact static file first
            file_path = STATIC_DIR / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html for client-side routing
            return FileResponse(STATIC_DIR / "index.html")

    return app
