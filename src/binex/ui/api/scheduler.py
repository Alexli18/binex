"""Scheduler API endpoints — status, history, start, stop, add, remove."""

from __future__ import annotations

import asyncio
import signal
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.scheduler.engine import scan_directory
from binex.scheduler.state import DEFAULT_STATE_PATH, load_state, save_state

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# Module-level scheduler subprocess reference
_scheduler_process: subprocess.Popen | None = None


def _get_state_path() -> Path:
    """Return state path (extracted for test patching)."""
    return DEFAULT_STATE_PATH


@router.get("/status")
async def scheduler_status() -> JSONResponse:
    """Return scheduler status and discovered workflows."""
    global _scheduler_process
    state_path = _get_state_path()

    running = _scheduler_process is not None and _scheduler_process.poll() is None
    pid = _scheduler_process.pid if running and _scheduler_process else None

    state = load_state(state_path)
    workflows = scan_directory(Path("."))

    return JSONResponse({
        "running": running,
        "pid": pid,
        "workflows": [
            {
                "name": wf.name,
                "path": wf.path,
                "schedule": wf.schedule,
                "next_run": wf.next_run.isoformat(),
            }
            for wf in workflows
        ],
        "registered_count": len(state.registered),
    })


@router.get("/history")
async def scheduler_history(limit: int = Query(50, ge=1, le=1000)) -> JSONResponse:
    """Return execution/skip history."""
    state_path = _get_state_path()
    state = load_state(state_path)
    entries = state.history[-limit:]
    entries.reverse()

    return JSONResponse({
        "history": [
            {
                "workflow": e.workflow,
                "timestamp": e.timestamp.isoformat(),
                "run_id": e.run_id,
                "status": e.status,
                "reason": e.reason,
                "duration_s": e.duration_s,
                "cost": e.cost,
            }
            for e in entries
        ],
    })


class StartRequest(BaseModel):
    directory: str = "."


@router.post("/start")
async def scheduler_start(req: StartRequest) -> JSONResponse:
    """Start the scheduler as a subprocess."""
    global _scheduler_process

    if _scheduler_process is not None and _scheduler_process.poll() is None:
        return JSONResponse({
            "status": "already_running",
            "pid": _scheduler_process.pid,
        })

    _scheduler_process = subprocess.Popen(
        [sys.executable, "-m", "binex", "scheduler", "start", req.directory],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return JSONResponse({
        "status": "started",
        "pid": _scheduler_process.pid,
    })


@router.post("/stop")
async def scheduler_stop() -> JSONResponse:
    """Stop the scheduler subprocess."""
    global _scheduler_process

    if _scheduler_process is None or _scheduler_process.poll() is not None:
        _scheduler_process = None
        return JSONResponse({"status": "not_running"})

    pid = _scheduler_process.pid
    _scheduler_process.send_signal(signal.SIGINT)
    try:
        await asyncio.to_thread(_scheduler_process.wait, timeout=30)
    except subprocess.TimeoutExpired:
        _scheduler_process.kill()
        await asyncio.to_thread(_scheduler_process.wait, timeout=5)
    _scheduler_process = None

    return JSONResponse({"status": "stopped", "pid": pid})


class WorkflowPathRequest(BaseModel):
    workflow_path: str


@router.post("/add")
async def scheduler_add(req: WorkflowPathRequest) -> JSONResponse:
    """Register a workflow for scheduling."""
    abs_path = str(Path(req.workflow_path).resolve())
    state_path = _get_state_path()
    state = load_state(state_path)

    if abs_path not in state.registered:
        state.registered.append(abs_path)
        save_state(state, state_path)

    return JSONResponse({"status": "registered", "path": abs_path})


@router.post("/remove")
async def scheduler_remove(req: WorkflowPathRequest) -> JSONResponse:
    """Unregister a workflow."""
    abs_path = str(Path(req.workflow_path).resolve())
    state_path = _get_state_path()
    state = load_state(state_path)

    if abs_path not in state.registered:
        return JSONResponse(
            status_code=404,
            content={"status": "not_found", "path": abs_path},
        )

    state.registered.remove(abs_path)
    save_state(state, state_path)
    return JSONResponse({"status": "removed", "path": abs_path})
