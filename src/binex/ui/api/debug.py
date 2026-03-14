"""Debug API endpoint for Binex Web UI."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from binex.cli import get_stores

router = APIRouter(prefix="/runs", tags=["debug"])


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


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

        # Try to load workflow spec for system_prompt info
        workflow_specs: dict[str, dict] = {}
        try:
            import yaml as _yaml
            from pathlib import Path

            wf_path = None
            # Try workflow_path first
            if run.workflow_path:
                p = Path(run.workflow_path)
                if not p.is_absolute():
                    p = Path.cwd() / p
                if p.exists():
                    wf_path = p

            # Fallback: search by workflow_name in cwd and examples
            if not wf_path and run.workflow_name:
                for search_dir in [Path.cwd(), Path.cwd() / "examples"]:
                    for f in search_dir.rglob("*.yaml"):
                        try:
                            d = _yaml.safe_load(f.read_text())
                            if isinstance(d, dict) and d.get("name") == run.workflow_name:
                                wf_path = f
                                break
                        except Exception:
                            continue
                    if wf_path:
                        break

            if wf_path:
                wf_data = _yaml.safe_load(wf_path.read_text())
                if isinstance(wf_data, dict) and "nodes" in wf_data:
                    workflow_specs = wf_data["nodes"]
        except Exception:
            pass

        # Index artifacts by produced_by node and by id
        arts_by_node: dict[str, list[dict]] = {}
        arts_by_id: dict[str, dict] = {}
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

        nodes = []
        for rec in records:
            status_str = rec.status.value if hasattr(rec.status, "value") else str(rec.status)

            # Calculate duration
            duration_s = rec.latency_ms / 1000.0 if rec.latency_ms else 0.0

            # Resolve input artifacts from refs
            input_arts = []
            for ref in (rec.input_artifact_refs or []):
                if ref in arts_by_id:
                    input_arts.append(arts_by_id[ref])

            node_data = {
                "node_id": rec.task_id,
                "status": status_str,
                "started_at": rec.timestamp.isoformat() if rec.timestamp else None,
                "completed_at": None,
                "duration_s": round(duration_s, 3),
                "error": rec.error,
                "agent": rec.agent_id,
                "system_prompt": rec.prompt or (
                    workflow_specs.get(rec.task_id, {}).get("system_prompt")
                    if isinstance(workflow_specs.get(rec.task_id), dict) else None
                ),
                "model": rec.model,
                "input_artifacts": input_arts,
                "artifacts": arts_by_node.get(rec.task_id, []),
            }
            nodes.append(node_data)

        # Apply filters
        if node is not None:
            nodes = [n for n in nodes if n["node_id"] == node]
        if errors_only:
            nodes = [n for n in nodes if n["status"] in ("failed", "timed_out")]

        return JSONResponse({
            "run_id": run.run_id,
            "status": run.status,
            "workflow_name": run.workflow_name,
            "workflow_path": run.workflow_path,
            "nodes": nodes,
        })
    finally:
        await exec_store.close()
