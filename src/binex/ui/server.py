"""FastAPI app factory for Binex Web UI."""

from __future__ import annotations

import pathlib

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from binex.ui.api.artifacts import router as artifacts_router
from binex.ui.api.bisect import router as bisect_router
from binex.ui.api.cost_dashboard import router as cost_dashboard_router
from binex.ui.api.costs import router as costs_router
from binex.ui.api.debug import router as debug_router
from binex.ui.api.diagnose import router as diagnose_router
from binex.ui.api.diff import router as diff_router
from binex.ui.api.estimate import router as estimate_router
from binex.ui.api.events import router as events_router
from binex.ui.api.export import router as export_router
from binex.ui.api.lineage import router as lineage_router
from binex.ui.api.runs import router as runs_router
from binex.ui.api.prompts import router as prompts_router
from binex.ui.api.scaffold import router as scaffold_router
from binex.ui.api.system import router as system_router
from binex.ui.api.trace import router as trace_router
from binex.ui.api.workflows import router as workflows_router

STATIC_DIR = pathlib.Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Binex Web UI", version="0.1.0")

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
    app.include_router(lineage_router, prefix="/api/v1")
    app.include_router(prompts_router, prefix="/api/v1")
    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(scaffold_router, prefix="/api/v1")
    app.include_router(system_router, prefix="/api/v1")
    app.include_router(trace_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")

    @app.get("/api/v1/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    # Mount static files and SPA fallback only if the static directory exists
    if STATIC_DIR.is_dir():
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
