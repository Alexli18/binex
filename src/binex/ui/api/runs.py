"""Runs API endpoints for Binex Web UI."""

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

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


class CreateRunRequest(BaseModel):
    """Request body for creating a new run."""

    workflow_path: str
    variables: dict[str, str] = {}


def _ensure_valid_spec(workflow_path: Path) -> None:
    """Patch workflow YAML to ensure it passes WorkflowSpec validation.

    Fixes common issues from the visual editor:
    - Missing 'outputs' field (required by WorkflowSpec)
    - 'inputs' as string instead of dict
    """
    import yaml as _yaml

    try:
        text = workflow_path.read_text()
        data = _yaml.safe_load(text)
        if not isinstance(data, dict) or "nodes" not in data:
            return
        patched = False
        for node_name, node_spec in data.get("nodes", {}).items():
            if not isinstance(node_spec, dict):
                continue
            if "outputs" not in node_spec:
                node_spec["outputs"] = ["output"]
                patched = True
            # Fix inputs: must be dict, not string
            inputs = node_spec.get("inputs")
            if isinstance(inputs, str):
                node_spec["inputs"] = {"input": inputs}
                patched = True
        if patched:
            workflow_path.write_text(
                _yaml.dump(data, indent=2, default_flow_style=False, sort_keys=False)
            )
    except Exception:
        pass  # Best effort — loader will report the real error


async def _execute_workflow(
    workflow_path: Path,
    variables: dict[str, str],
    run_id: str | None = None,
) -> dict:
    """Load and execute a workflow through the real orchestrator."""
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.orchestrator import Orchestrator
    from binex.workflow_spec.loader import load_workflow
    from binex.workflow_spec.validator import validate_workflow

    _ensure_valid_spec(workflow_path)
    spec = load_workflow(str(workflow_path), user_vars=variables or None)

    errors = validate_workflow(spec)
    if errors:
        return {"error": "; ".join(errors), "status_code": 422}

    exec_store, artifact_store = _get_stores()

    async def _on_event(evt: dict) -> None:
        rid = evt.get("run_id", run_id)
        if rid:
            await event_bus.publish(rid, evt)

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=exec_store,
        stream=False,
        event_callback=_on_event,
    )

    plugin_registry = PluginRegistry()
    plugin_registry.discover()

    register_workflow_adapters(
        orch.dispatcher, spec, plugin_registry=plugin_registry,
        web_mode=True,
    )

    try:
        summary = await orch.run_workflow(spec, run_id=run_id)
        return {"run_id": summary.run_id, "status": summary.status}
    finally:
        await exec_store.close()


async def _execute_workflow_background(
    run_id: str, workflow_path: Path, variables: dict[str, str],
) -> None:
    """Execute workflow in background, publishing SSE events."""
    try:
        result = await _execute_workflow(workflow_path, variables, run_id=run_id)
        status = result.get("status", "failed")
        if "error" in result:
            await event_bus.publish(run_id, {
                "type": "run:completed",
                "status": "failed",
                "error": result["error"],
                "timestamp": _now_iso(),
            })
        else:
            await event_bus.publish(run_id, {
                "type": "run:completed",
                "status": status,
                "timestamp": _now_iso(),
            })
    except Exception as exc:
        logger.exception("Background workflow execution failed")
        await event_bus.publish(run_id, {
            "type": "run:completed",
            "status": "failed",
            "error": str(exc),
            "timestamp": _now_iso(),
        })


def _now_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


@router.post("", status_code=201)
async def create_run(body: CreateRunRequest) -> JSONResponse:
    """Create and execute a new workflow run.

    For workflows without human nodes, the run completes before the response.
    For human-in-the-loop workflows, returns immediately with run_id and
    status 'running', then executes in the background.
    """
    workflow = Path(body.workflow_path)
    if not workflow.is_absolute():
        workflow = Path.cwd() / workflow
    if not workflow.exists():
        return JSONResponse(
            {"error": f"Workflow file '{body.workflow_path}' not found"},
            status_code=404,
        )

    # Check if workflow contains human:// nodes (needs async execution)
    try:
        text = workflow.read_text()
    except OSError:
        text = ""

    has_human_nodes = "human://" in text

    if has_human_nodes:
        # Launch in background so the browser can subscribe to SSE first
        run_id = f"run_{uuid4().hex[:12]}"
        asyncio.create_task(
            _execute_workflow_background(run_id, workflow, body.variables),
        )
        return JSONResponse(
            {"run_id": run_id, "status": "running"},
            status_code=201,
        )

    # Non-human workflow: execute synchronously
    try:
        result = await _execute_workflow(workflow, body.variables)
    except Exception as exc:
        logger.exception("Workflow execution failed")
        return JSONResponse(
            {"error": f"Workflow execution failed: {exc}"},
            status_code=422,
        )

    if "error" in result:
        return JSONResponse(
            {"error": result["error"]},
            status_code=result.get("status_code", 422),
        )

    return JSONResponse(
        {"run_id": result["run_id"], "status": result["status"]},
        status_code=201,
    )


class ReplayRequest(BaseModel):
    run_id: str
    from_step: str
    workflow_path: str
    agent_swaps: dict[str, str] = {}


@router.post("/replay")
async def replay_run(body: ReplayRequest) -> JSONResponse:
    """Replay a run from a specific step with optional agent swaps."""
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.replay import ReplayEngine
    from binex.workflow_spec.loader import load_workflow

    workflow = Path(body.workflow_path)
    if not workflow.is_absolute():
        workflow = Path.cwd() / workflow
    if not workflow.exists():
        return JSONResponse({"error": f"Workflow '{body.workflow_path}' not found"}, status_code=404)

    new_run_id = f"run_{uuid4().hex[:12]}"

    async def _bg():
        exec_store, artifact_store = _get_stores()
        try:
            _ensure_valid_spec(workflow)
            spec = load_workflow(str(workflow))
            engine = ReplayEngine(execution_store=exec_store, artifact_store=artifact_store)
            plugin_registry = PluginRegistry()
            plugin_registry.discover()
            register_workflow_adapters(engine.dispatcher, spec, agent_swaps=body.agent_swaps, plugin_registry=plugin_registry, web_mode=True)
            summary = await engine.replay(original_run_id=body.run_id, workflow=spec, from_step=body.from_step, agent_swaps=body.agent_swaps)
            await event_bus.publish(new_run_id, {"type": "run:completed", "status": summary.status, "timestamp": _now_iso()})
        except Exception as exc:
            logger.exception("Replay failed")
            await event_bus.publish(new_run_id, {"type": "run:completed", "status": "failed", "error": str(exc), "timestamp": _now_iso()})
        finally:
            await exec_store.close()

    asyncio.create_task(_bg())
    return JSONResponse({"run_id": new_run_id, "status": "running", "replaying_from": body.from_step}, status_code=201)


@router.get("")
async def list_runs() -> JSONResponse:
    """List all workflow runs."""
    exec_store, _ = _get_stores()
    runs = await exec_store.list_runs()
    return JSONResponse({"runs": [r.model_dump(mode="json") for r in runs]})


@router.get("/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    """Get a single workflow run by ID."""
    exec_store, _ = _get_stores()
    run = await exec_store.get_run(run_id)
    if run is None:
        return JSONResponse({"error": f"Run '{run_id}' not found"}, status_code=404)
    return JSONResponse(run.model_dump(mode="json"))


@router.get("/{run_id}/records")
async def get_records(run_id: str) -> JSONResponse:
    """Get execution records for a workflow run."""
    exec_store, _ = _get_stores()
    records = await exec_store.list_records(run_id)
    return JSONResponse({"records": [r.model_dump(mode="json") for r in records]})


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str) -> JSONResponse:
    """Cancel a running workflow run."""
    exec_store, _ = _get_stores()
    run = await exec_store.get_run(run_id)
    if run is None:
        return JSONResponse(
            {"error": f"Run '{run_id}' not found"}, status_code=404
        )
    if run.status != "running":
        return JSONResponse(
            {"error": f"Run '{run_id}' is not running (status: {run.status})"},
            status_code=409,
        )
    run_updated = run.model_copy(update={"status": "cancelled"})
    await exec_store.update_run(run_updated)
    return JSONResponse({"run_id": run_id, "status": "cancelled"})
