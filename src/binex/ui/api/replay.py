"""Replay API endpoint for Binex Web UI."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.cli import get_stores
from binex.ui.api.events import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["replay"])


class ReplayRequest(BaseModel):
    """Request body for replaying a run from a specific step."""

    run_id: str
    from_step: str
    workflow_path: str
    agent_swaps: dict[str, str] = {}


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


async def _execute_replay(
    run_id: str,
    from_step: str,
    workflow_path: str,
    agent_swaps: dict[str, str],
    new_run_id: str,
) -> dict:
    """Load and execute a replay through the ReplayEngine."""
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.replay import ReplayEngine
    from binex.workflow_spec.loader import load_workflow

    exec_store, artifact_store = _get_stores()

    spec = load_workflow(workflow_path)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=artifact_store,
    )

    plugin_registry = PluginRegistry()
    plugin_registry.discover()

    register_workflow_adapters(
        engine.dispatcher,
        spec,
        agent_swaps=agent_swaps,
        plugin_registry=plugin_registry,
        web_mode=True,
    )

    try:
        summary = await engine.replay(
            original_run_id=run_id,
            workflow=spec,
            from_step=from_step,
            agent_swaps=agent_swaps,
        )
        return {"run_id": summary.run_id, "status": summary.status}
    finally:
        await exec_store.close()


async def _replay_background(
    run_id: str,
    from_step: str,
    workflow_path: str,
    agent_swaps: dict[str, str],
    new_run_id: str,
) -> None:
    """Execute replay in background, publishing SSE events."""
    try:
        result = await _execute_replay(
            run_id, from_step, workflow_path, agent_swaps, new_run_id,
        )
        await event_bus.publish(new_run_id, {
            "type": "run:completed",
            "status": result.get("status", "completed"),
            "timestamp": _now_iso(),
        })
    except Exception as exc:
        logger.exception("Replay failed")
        await event_bus.publish(new_run_id, {
            "type": "run:completed",
            "status": "failed",
            "error": str(exc),
            "timestamp": _now_iso(),
        })


@router.post("/replay")
async def replay_run(body: ReplayRequest) -> JSONResponse:
    """Replay a run from a specific step with optional agent swaps."""
    workflow = Path(body.workflow_path)
    if not workflow.is_absolute():
        workflow = Path.cwd() / workflow
    if not workflow.exists():
        return JSONResponse(
            {"error": f"Workflow file '{body.workflow_path}' not found"},
            status_code=404,
        )

    new_run_id = f"run_{uuid4().hex[:12]}"

    # Execute in background so the browser can subscribe to SSE first
    asyncio.create_task(
        _replay_background(
            body.run_id, body.from_step, str(workflow),
            body.agent_swaps, new_run_id,
        ),
    )

    return JSONResponse(
        {
            "run_id": new_run_id,
            "status": "running",
            "replaying_from": body.from_step,
        },
        status_code=201,
    )
