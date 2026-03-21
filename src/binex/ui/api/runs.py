"""Runs API endpoints for Binex Web UI."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.cli import get_stores
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore
from binex.ui.api.errors import APIError
from binex.ui.api.events import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


class CreateRunRequest(BaseModel):
    """Request body for creating a new run."""

    workflow_path: str
    variables: dict[str, str] = {}


def _normalize_spec_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a parsed workflow dict so it passes WorkflowSpec validation.

    Fixes common issues produced by the visual editor without touching the
    YAML file on disk:

    - Missing ``outputs`` field (required by NodeSpec) -- defaults to ``["output"]``
    - ``inputs`` given as a bare string instead of a dict
    """
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        return data
    for node_spec in nodes.values():
        if not isinstance(node_spec, dict):
            continue
        if "outputs" not in node_spec:
            node_spec["outputs"] = ["output"]
        inputs = node_spec.get("inputs")
        if isinstance(inputs, str):
            node_spec["inputs"] = {"input": inputs}
    return data


async def _execute_workflow(
    workflow_path: Path,
    variables: dict[str, str],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Load and execute a workflow through the real orchestrator."""
    import yaml as _yaml  # type: ignore[import-untyped]

    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.orchestrator import Orchestrator
    from binex.workflow_spec.loader import load_workflow_from_string
    from binex.workflow_spec.validator import validate_workflow

    # Read, normalize in memory, and parse -- no file mutation.
    raw_text = workflow_path.read_text()
    raw_data = _yaml.safe_load(raw_text)
    if isinstance(raw_data, dict) and "nodes" in raw_data:
        _normalize_spec_data(raw_data)
        # Re-serialize so load_workflow_from_string gets the normalized text
        normalized_text = _yaml.dump(
            raw_data, indent=2, default_flow_style=False, sort_keys=False,
        )
    else:
        normalized_text = raw_text

    spec = load_workflow_from_string(
        normalized_text, fmt="yaml", user_vars=variables or None,
        base_dir=workflow_path.parent,
    )
    spec.source_path = str(workflow_path)

    errors = validate_workflow(spec)
    if errors:
        return {"error": "; ".join(errors), "status_code": 422}

    exec_store, artifact_store = _get_stores()

    async def _on_event(evt: dict[str, Any]) -> None:
        rid = evt.get("run_id", run_id)
        if rid:
            await event_bus.publish(rid, evt)

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=exec_store,
        stream=False,
        event_callback=_on_event,
        interactive=False,
    )

    plugin_registry = PluginRegistry()
    plugin_registry.discover()

    register_workflow_adapters(
        orch.dispatcher, spec, plugin_registry=plugin_registry,
        web_mode=True,
        event_callback=orch._event_callback,
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
        raise APIError(
            404, "workflow_not_found",
            f"Workflow file '{body.workflow_path}' not found",
        )

    # Check if workflow contains human:// nodes (needs async execution)
    try:
        text = workflow.read_text()
    except OSError:
        text = ""

    has_human_nodes = "human://" in text

    if has_human_nodes:
        # Pre-create run record so the live page can find it immediately
        run_id = f"run_{uuid4().hex[:12]}"
        try:
            import yaml as _yaml

            from binex.models import RunSummary
            from binex.workflow_spec.loader import load_workflow_from_string

            raw_data = _yaml.safe_load(text)
            if isinstance(raw_data, dict) and "nodes" in raw_data:
                _normalize_spec_data(raw_data)
                normalized = _yaml.dump(
                    raw_data, indent=2, default_flow_style=False, sort_keys=False,
                )
            else:
                normalized = text
            spec = load_workflow_from_string(normalized, fmt="yaml", base_dir=workflow.parent)
            total_nodes = len(spec.nodes)
            wf_name = spec.name
        except Exception:
            total_nodes = text.count("agent:")
            wf_name = workflow.stem

        exec_store, _ = _get_stores()
        try:
            from binex.models import RunSummary

            summary = RunSummary(
                run_id=run_id,
                workflow_name=wf_name,
                workflow_path=str(workflow),
                status="running",
                total_nodes=total_nodes,
            )
            await exec_store.create_run(summary)
        finally:
            await exec_store.close()

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
        raise APIError(
            422, "execution_failed",
            f"Workflow execution failed: {exc}",
        ) from exc

    if "error" in result:
        raise APIError(
            result.get("status_code", 422),
            "validation_error",
            result["error"],
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
    import yaml as _yaml

    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.replay import ReplayEngine
    from binex.workflow_spec.loader import load_workflow_from_string

    workflow = Path(body.workflow_path)
    if not workflow.is_absolute():
        workflow = Path.cwd() / workflow
    if not workflow.exists():
        raise APIError(
            404, "workflow_not_found",
            f"Workflow '{body.workflow_path}' not found",
        )

    exec_store, artifact_store = _get_stores()
    try:
        raw_text = workflow.read_text()
        raw_data = _yaml.safe_load(raw_text)
        if isinstance(raw_data, dict) and "nodes" in raw_data:
            _normalize_spec_data(raw_data)
            normalized_text = _yaml.dump(
                raw_data, indent=2, default_flow_style=False, sort_keys=False,
            )
        else:
            normalized_text = raw_text

        spec = load_workflow_from_string(
            normalized_text, fmt="yaml", base_dir=workflow.parent,
        )
        spec.source_path = str(workflow)

        engine = ReplayEngine(
            execution_store=exec_store, artifact_store=artifact_store,
        )
        plugin_registry = PluginRegistry()
        plugin_registry.discover()
        register_workflow_adapters(
            engine.dispatcher, spec,
            agent_swaps=body.agent_swaps,
            plugin_registry=plugin_registry,
        )
        summary = await engine.replay(
            original_run_id=body.run_id,
            workflow=spec,
            from_step=body.from_step,
            agent_swaps=body.agent_swaps,
        )
        return JSONResponse(
            {"run_id": summary.run_id, "status": summary.status},
            status_code=201,
        )
    except APIError:
        raise
    except Exception as exc:
        logger.exception("Replay failed")
        raise APIError(
            422, "replay_failed", f"Replay failed: {exc}",
        ) from exc
    finally:
        await exec_store.close()


@router.get("")
async def list_runs() -> JSONResponse:
    """List all workflow runs."""
    exec_store, _ = _get_stores()
    try:
        runs = await exec_store.list_runs()
        return JSONResponse({"runs": [r.model_dump(mode="json") for r in runs]})
    finally:
        await exec_store.close()


@router.get("/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    """Get a single workflow run by ID."""
    exec_store, _ = _get_stores()
    try:
        run = await exec_store.get_run(run_id)
        if run is None:
            raise APIError(404, "run_not_found", f"Run '{run_id}' not found")
        return JSONResponse(run.model_dump(mode="json"))
    finally:
        await exec_store.close()


@router.get("/{run_id}/records")
async def get_records(run_id: str) -> JSONResponse:
    """Get execution records for a workflow run."""
    exec_store, _ = _get_stores()
    try:
        records = await exec_store.list_records(run_id)
        return JSONResponse({"records": [r.model_dump(mode="json") for r in records]})
    finally:
        await exec_store.close()


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: str) -> JSONResponse:
    """Cancel a running workflow run."""
    exec_store, _ = _get_stores()
    try:
        run = await exec_store.get_run(run_id)
        if run is None:
            raise APIError(404, "run_not_found", f"Run '{run_id}' not found")
        if run.status != "running":
            raise APIError(
                409, "run_not_running",
                f"Run '{run_id}' is not running (status: {run.status})",
            )
        run_updated = run.model_copy(update={"status": "cancelled"})
        await exec_store.update_run(run_updated)
        return JSONResponse({"run_id": run_id, "status": "cancelled"})
    finally:
        await exec_store.close()
