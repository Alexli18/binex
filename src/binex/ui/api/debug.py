"""Debug API endpoint for Binex Web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from binex.cli import get_stores
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore
from binex.stores.backends.filesystem import FilesystemArtifactStore

router = APIRouter(prefix="/runs", tags=["debug"])


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _resolve_workflow_path(run: Any) -> Path | None:
    """Resolve workflow YAML path from run metadata."""
    # Try workflow_path first
    if run.workflow_path:
        p = Path(run.workflow_path)
        if not p.is_absolute():
            p = Path.cwd() / p
        if p.exists():
            return p

    # Fallback: search by workflow_name in cwd and examples
    if not run.workflow_name:
        return None

    import yaml as _yaml  # type: ignore[import-untyped]

    for search_dir in [Path.cwd(), Path.cwd() / "examples"]:
        for f in search_dir.rglob("*.yaml"):
            try:
                d = _yaml.safe_load(f.read_text())
                if isinstance(d, dict) and d.get("name") == run.workflow_name:
                    return f
            except Exception:
                continue
    return None


def _load_workflow_node_specs(run: Any) -> dict[str, dict[str, Any]]:
    """Load workflow node specs from YAML for system_prompt fallback."""
    try:
        import yaml as _yaml

        wf_path = _resolve_workflow_path(run)
        if not wf_path:
            return {}
        wf_data = _yaml.safe_load(wf_path.read_text())
        if isinstance(wf_data, dict) and "nodes" in wf_data:
            nodes: dict[str, dict[str, Any]] = wf_data["nodes"]
            return nodes
    except Exception:
        pass
    return {}


def _index_artifacts(artifacts: Any) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Index artifacts by producer node and by artifact ID."""
    arts_by_node: dict[str, list[dict[str, Any]]] = {}
    arts_by_id: dict[str, dict[str, Any]] = {}
    for art in artifacts:
        art_dict = {
            "id": art.id,
            "type": art.type,
            "content": art.content,
            "produced_by": art.lineage.produced_by,
        }
        producer = art.lineage.produced_by
        arts_by_node.setdefault(producer, []).append(art_dict)
        arts_by_id[art.id] = art_dict
    return arts_by_node, arts_by_id


def _resolve_system_prompt(rec: Any, workflow_specs: dict[str, dict[str, Any]]) -> str | None:
    """Resolve system_prompt from execution record or workflow spec fallback."""
    if rec.prompt:
        return str(rec.prompt)
    node_spec = workflow_specs.get(rec.task_id)
    if isinstance(node_spec, dict):
        val = node_spec.get("system_prompt")
        return str(val) if val is not None else None
    return None


def _build_node_data(
    rec: Any,
    workflow_specs: dict[str, dict[str, Any]],
    arts_by_node: dict[str, list[dict[str, Any]]],
    arts_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a single node debug data dict from an execution record."""
    status_str = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
    duration_s = rec.latency_ms / 1000.0 if rec.latency_ms else 0.0

    input_arts = [
        arts_by_id[ref]
        for ref in (rec.input_artifact_refs or [])
        if ref in arts_by_id
    ]

    return {
        "node_id": rec.task_id,
        "status": status_str,
        "started_at": rec.timestamp.isoformat() if rec.timestamp else None,
        "completed_at": None,
        "duration_s": round(duration_s, 3),
        "error": rec.error,
        "agent": rec.agent_id,
        "system_prompt": _resolve_system_prompt(rec, workflow_specs),
        "model": rec.model,
        "input_artifacts": input_arts,
        "artifacts": arts_by_node.get(rec.task_id, []),
    }


def _apply_filters(
    nodes: list[dict[str, Any]], node_filter: str | None, errors_only: bool,
) -> list[dict[str, Any]]:
    """Apply optional node and error filters."""
    if node_filter is not None:
        nodes = [n for n in nodes if n["node_id"] == node_filter]
    if errors_only:
        nodes = [n for n in nodes if n["status"] in ("failed", "timed_out")]
    return nodes


@router.get("/{run_id}/debug")
async def get_debug(
    run_id: str,
    errors_only: bool = Query(False),
    node: str | None = Query(None),
) -> JSONResponse:
    """Post-mortem debug view of a workflow run."""
    exec_store, art_store = _get_stores()
    try:
        run = await exec_store.get_run(run_id)
        if run is None:
            return JSONResponse(
                {"error": f"Run '{run_id}' not found"}, status_code=404,
            )

        records = await exec_store.list_records(run_id)
        artifacts = await art_store.list_by_run(run_id)

        workflow_specs = _load_workflow_node_specs(run)
        arts_by_node, arts_by_id = _index_artifacts(artifacts)

        nodes = [
            _build_node_data(rec, workflow_specs, arts_by_node, arts_by_id)
            for rec in records
        ]
        nodes = _apply_filters(nodes, node, errors_only)

        return JSONResponse({
            "run_id": run.run_id,
            "status": run.status,
            "workflow_name": run.workflow_name,
            "workflow_path": run.workflow_path,
            "nodes": nodes,
        })
    finally:
        await exec_store.close()
