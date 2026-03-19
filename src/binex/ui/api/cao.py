"""CAO (CLI Agent Orchestrator) adapter API.

Endpoints for managing CAO sessions — handoff tracking, session lifecycle,
debug introspection, and orphan detection.  Consumed by the Web UI for:
- RunDetail / RunLive CAO debug panels
- Editor CAO node configuration (profile dropdown)
- Dashboard orphaned-session warnings
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cao", tags=["cao"])


class TerminalInputRequest(BaseModel):
    message: str


def _get_stores():
    """Lazy import to avoid circular deps — patchable in tests."""
    from binex.cli import get_stores

    return get_stores()


# ---------------------------------------------------------------------------
# GET /cao/profiles — list installed CAO agent profiles from filesystem
# ---------------------------------------------------------------------------

@router.get("/profiles")
async def list_profiles() -> JSONResponse:
    """List available CAO profiles from the agent-store directory."""
    settings = Settings()
    store_dir = settings.cao_agent_store_dir

    if not os.path.isdir(store_dir):
        return JSONResponse(
            status_code=200,
            content={
                "profiles": [],
                "agent_store_dir": store_dir,
                "warning": f"Agent store not found at {store_dir}",
            },
        )

    profiles = sorted(
        Path(f).stem
        for f in Path(store_dir).glob("*.md")
        if f.is_file()
    )

    return JSONResponse(
        content={
            "profiles": profiles,
            "agent_store_dir": store_dir,
        },
    )


# ---------------------------------------------------------------------------
# GET /cao/sessions — list all CAO sessions from SQLite
# ---------------------------------------------------------------------------

@router.get("/sessions")
async def list_sessions() -> JSONResponse:
    """Return all CAO sessions from the session registry."""
    exec_store, _ = _get_stores()
    try:
        sessions = await exec_store.get_cao_sessions()
        return JSONResponse(content={"sessions": sessions})
    finally:
        await exec_store.close()


# ---------------------------------------------------------------------------
# DELETE /cao/sessions/{terminal_id} — cleanup a session
# ---------------------------------------------------------------------------

@router.delete("/sessions/{terminal_id}")
async def delete_session(terminal_id: str) -> JSONResponse:
    """Terminate and remove a CAO session."""
    exec_store, _ = _get_stores()
    try:
        # Try to terminate on CAO server (best-effort)
        settings = Settings()
        server_url = settings.cao_server_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    await client.post(f"{server_url}/terminals/{terminal_id}/exit")
                except httpx.HTTPError:
                    pass
                try:
                    await client.delete(f"{server_url}/terminals/{terminal_id}")
                except httpx.HTTPError:
                    pass
        except Exception:
            logger.debug("Failed to cleanup terminal %s on CAO server", terminal_id)

        # Remove from SQLite
        deleted = await exec_store.delete_cao_session(terminal_id)
        if not deleted:
            return JSONResponse(
                status_code=404,
                content={"error": "session not found"},
            )
        return JSONResponse(content={"ok": True})
    finally:
        await exec_store.close()


# ---------------------------------------------------------------------------
# POST /cao/terminals/{terminal_id}/input — forward user input (HITL)
# ---------------------------------------------------------------------------

@router.post("/terminals/{terminal_id}/input")
async def send_terminal_input(
    terminal_id: str, body: TerminalInputRequest,
) -> JSONResponse:
    """Forward user input to a CAO terminal (human-in-the-loop)."""
    settings = Settings()
    server_url = settings.cao_server_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{server_url}/terminals/{terminal_id}/input",
                data={"message": body.message},
            )
            resp.raise_for_status()
            return JSONResponse(content={"ok": True})
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": f"CAO server error: {exc}"},
        )
