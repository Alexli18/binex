"""System API endpoints for Binex Web UI."""

from __future__ import annotations

import sys

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/system", tags=["system"])


_BUILTIN_ADAPTERS = [
    {"name": "local", "type": "adapter", "builtin": True, "description": "Local Python agent"},
    {"name": "llm", "type": "adapter", "builtin": True, "description": "LLM via litellm"},
    {"name": "human", "type": "adapter", "builtin": True, "description": "Human approval"},
    {"name": "a2a", "type": "adapter", "builtin": True, "description": "A2A remote agent"},
]

_DEFAULT_GATEWAY_URL = "http://localhost:8421"


@router.get("/doctor")
async def doctor() -> JSONResponse:
    """Run basic health checks on the Binex environment."""
    checks = []

    # Python version
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    checks.append({
        "name": "Python Version",
        "status": "ok" if py_ok else "warn",
        "message": version if py_ok else f"{version} (3.11+ recommended)",
    })

    # SQLite store
    try:
        from binex.cli import get_stores
        exec_store, _ = get_stores()
        await exec_store.close()
        checks.append({
            "name": "SQLite Store",
            "status": "ok",
            "message": "Connected",
        })
    except Exception as exc:
        checks.append({
            "name": "SQLite Store",
            "status": "error",
            "message": str(exc),
        })

    # Artifact store
    try:
        from pathlib import Path
        artifacts_dir = Path(".binex/artifacts")
        if artifacts_dir.exists():
            checks.append({
                "name": "Artifact Store",
                "status": "ok",
                "message": ".binex/artifacts/ exists",
            })
        else:
            checks.append({
                "name": "Artifact Store",
                "status": "warn",
                "message": ".binex/artifacts/ not found (will be created on first run)",
            })
    except Exception as exc:
        checks.append({
            "name": "Artifact Store",
            "status": "error",
            "message": str(exc),
        })

    # LiteLLM
    try:
        import litellm  # noqa: F401
        checks.append({
            "name": "LiteLLM",
            "status": "ok",
            "message": "Available",
        })
    except ImportError:
        checks.append({
            "name": "LiteLLM",
            "status": "error",
            "message": "Not installed (pip install litellm)",
        })

    return JSONResponse({"checks": checks})


@router.get("/plugins")
async def list_plugins() -> JSONResponse:
    """List built-in adapters and installed plugins."""
    plugins = list(_BUILTIN_ADAPTERS)

    # Discover installed plugins via entry points
    try:
        from binex.plugins import PluginRegistry
        registry = PluginRegistry()
        registry.discover()
        for p in registry.all_plugins():
            plugins.append({
                "name": p["prefix"],
                "type": "adapter",
                "builtin": False,
                "description": p.get("package_name", p.get("name", "")),
            })
    except Exception:
        pass  # Plugin discovery is best-effort

    return JSONResponse({"plugins": plugins})


@router.get("/gateway")
async def gateway_status() -> JSONResponse:
    """Check A2A gateway connectivity."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{_DEFAULT_GATEWAY_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                agents = data.get("agents", [])
                return JSONResponse({
                    "status": "online",
                    "agents": agents,
                    "message": f"Gateway running, {len(agents)} agent(s) registered",
                })
            else:
                return JSONResponse({
                    "status": "error",
                    "agents": [],
                    "message": f"Gateway returned status {resp.status_code}",
                })
    except Exception:
        return JSONResponse({
            "status": "offline",
            "agents": [],
            "message": "Gateway not running",
        })
