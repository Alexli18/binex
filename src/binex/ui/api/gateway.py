"""Gateway API endpoints — start, stop, status (subprocess management)."""

from __future__ import annotations

import asyncio
import signal
import subprocess
import sys

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/gateway", tags=["gateway"])

# Module-level gateway subprocess reference
_gateway_process: subprocess.Popen[bytes] | None = None


class GatewayStartRequest(BaseModel):
    config: str | None = None
    host: str | None = None
    port: int | None = None


@router.post("/start")
async def gateway_start(req: GatewayStartRequest) -> JSONResponse:
    """Start the A2A gateway as a subprocess."""
    global _gateway_process

    if _gateway_process is not None and _gateway_process.poll() is None:
        return JSONResponse({
            "status": "already_running",
            "pid": _gateway_process.pid,
        })

    cmd = [sys.executable, "-m", "binex", "gateway"]
    if req.config:
        cmd.extend(["--config", req.config])
    if req.host:
        cmd.extend(["--host", req.host])
    if req.port is not None:
        cmd.extend(["--port", str(req.port)])

    _gateway_process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return JSONResponse({
        "status": "started",
        "pid": _gateway_process.pid,
    })


@router.post("/stop")
async def gateway_stop() -> JSONResponse:
    """Stop the gateway subprocess."""
    global _gateway_process

    if _gateway_process is None or _gateway_process.poll() is not None:
        _gateway_process = None
        return JSONResponse({"status": "not_running"})

    pid = _gateway_process.pid
    _gateway_process.send_signal(signal.SIGINT)

    try:
        await asyncio.to_thread(_gateway_process.wait, timeout=30)
    except subprocess.TimeoutExpired:
        _gateway_process.kill()
        await asyncio.to_thread(_gateway_process.wait, timeout=5)

    _gateway_process = None
    return JSONResponse({"status": "stopped", "pid": pid})


@router.get("/process-status")
async def gateway_process_status() -> JSONResponse:
    """Check if the gateway subprocess is running."""
    global _gateway_process

    running = _gateway_process is not None and _gateway_process.poll() is None
    pid = _gateway_process.pid if running and _gateway_process else None

    return JSONResponse({
        "running": running,
        "pid": pid,
    })
