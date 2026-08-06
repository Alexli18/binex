"""MCP tool handler implementations.

Each handler is a plain async function taking stores and typed parameters.
They are testable without MCP transport — the server in ``server.py`` simply
wires them up.

All handlers return JSON-serialisable dicts.  On error they return::

    {"error": "<human message>", "code": "<not_found|invalid_input|unsupported|execution_error>"}

Artifact content anywhere in a response is truncated to 4 000 characters with
a pointer to ``get_artifact`` for full content.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore

_TRUNCATE_AT = 4_000
_TRUNCATE_SUFFIX = (
    "... [truncated {remaining} chars — use get_artifact('{art_id}') for full content]"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _truncate(content: str, art_id: str = "") -> str:
    """Truncate *content* at ``_TRUNCATE_AT`` chars with a pointer suffix."""
    if len(content) <= _TRUNCATE_AT:
        return content
    remaining = len(content) - _TRUNCATE_AT
    suffix = _TRUNCATE_SUFFIX.format(remaining=remaining, art_id=art_id)
    return content[:_TRUNCATE_AT] + suffix


def _artifact_dict(art: Any, truncate: bool = True) -> dict[str, Any]:
    """Convert an Artifact to a serialisable dict."""
    content = art.content or ""
    if isinstance(content, (dict, list)):
        import json as _json
        content = _json.dumps(content)
    if truncate:
        content = _truncate(str(content), art.id)
    return {
        "id": art.id,
        "type": art.type,
        "content": content,
        "produced_by": art.lineage.produced_by if art.lineage else None,
    }


def _run_to_status(run: Any) -> dict[str, Any]:
    """Serialise a RunSummary to the status dict shape used by multiple tools."""
    return {
        "run_id": run.run_id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "completed_nodes": run.completed_nodes,
        "failed_nodes": run.failed_nodes,
        "skipped_nodes": run.skipped_nodes,
        "total_cost": run.total_cost,
        "source": run.source,
    }


# ---------------------------------------------------------------------------
# Workflow-loading helpers for replay/run (T021)
# ---------------------------------------------------------------------------

async def _load_workflow_for_replay(
    run: Any,
    exec_store: ExecutionStore,
) -> Any:
    """Load a ``WorkflowSpec`` for a given run.

    Resolution order:
    1. ``run.workflow_path`` (filesystem).
    2. ``workflow_snapshots`` table via ``run.workflow_hash`` (stored spec).

    Returns a ``WorkflowSpec`` or raises ``ValueError`` if not resolvable.
    """
    from binex.workflow_spec.loader import load_workflow

    if run.workflow_path:
        path = Path(run.workflow_path)
        if path.exists():
            return load_workflow(str(path))

    # Fallback: workflow snapshot stored at run time
    if run.workflow_hash:
        snapshot = await exec_store.get_workflow_snapshot(run.workflow_hash)
        if snapshot:
            import yaml  # type: ignore[import-untyped]

            data = yaml.safe_load(snapshot["content"])
            from binex.models.workflow import WorkflowSpec

            return WorkflowSpec(**data)

    raise ValueError(
        f"Cannot locate workflow for run '{run.run_id}': "
        "neither workflow_path exists on disk nor a stored snapshot is available."
    )


def _apply_node_prompt_override(
    spec: Any,
    node_id: str,
    prompt: str,
) -> Any:
    """Return a deep copy of *spec* with *node_id*'s ``system_prompt`` replaced.

    This is a pure transformation — the original spec is never mutated.
    Raises ``ValueError`` if *node_id* is not in the spec.
    """
    if node_id not in spec.nodes:
        raise ValueError(f"Node '{node_id}' not found in workflow spec.")

    # Deep-copy via Pydantic round-trip to avoid shared state
    data = copy.deepcopy(spec.model_dump())
    data["nodes"][node_id]["system_prompt"] = prompt

    from binex.models.workflow import WorkflowSpec

    return WorkflowSpec(**data)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def list_workflows(
    exec_store: ExecutionStore,  # noqa: ARG001 — kept for consistent signature
    art_store: ArtifactStore,  # noqa: ARG001
    base_dir: str | None = None,
) -> dict[str, Any]:
    """Discover workflow files (same logic as ``binex list``).

    Returns ``{"workflows": [{"path", "name", "description?"}]}``.
    """
    from pathlib import Path as _Path

    from binex.workflow_spec.discovery import (
        get_examples_dir,
        scan_workflow_details,
        scan_workflow_files,
    )

    base = _Path(base_dir) if base_dir else _Path.cwd()
    rel_paths = scan_workflow_files(base)

    if not rel_paths:
        examples_dir = get_examples_dir()
        if examples_dir:
            rel_paths = [f"examples/{r}" for r in scan_workflow_files(examples_dir)]

    workflows: list[dict[str, Any]] = []
    for rel in rel_paths:
        # Resolve absolute path to extract name/description via YAML parse
        if rel.startswith("examples/"):
            examples_dir = get_examples_dir()
            if examples_dir:
                abs_path = examples_dir / rel[len("examples/"):]
            else:
                workflows.append({"path": rel, "name": rel})
                continue
        else:
            abs_path = base / rel

        details = scan_workflow_details(abs_path.parent)
        match = next((d for d in details if d["path"] == str(abs_path)), None)
        if match:
            entry: dict[str, Any] = {"path": rel, "name": match["name"]}
            if match.get("description"):
                entry["description"] = match["description"]
            workflows.append(entry)
        else:
            workflows.append({"path": rel, "name": rel})

    return {"workflows": workflows}


async def run_workflow(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    path: str,
    inputs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run a workflow synchronously to completion with scripted inputs."""
    from binex.adapters.scripted_input import ScriptedInputAdapter
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.orchestrator import Orchestrator
    from binex.workflow_spec.discovery import resolve_workflow_path
    from binex.workflow_spec.loader import load_workflow

    resolved = resolve_workflow_path(path)
    if resolved is None:
        return {"error": f"Workflow '{path}' not found", "code": "not_found"}

    try:
        spec = load_workflow(str(resolved))
    except Exception as exc:
        return {"error": f"Failed to load workflow: {exc}", "code": "invalid_input"}

    plugin_registry = PluginRegistry()
    plugin_registry.discover()

    scripted = ScriptedInputAdapter(inputs or {})
    orchestrator = Orchestrator(
        execution_store=exec_store,
        artifact_store=art_store,
        interactive=False,
    )

    dispatcher = orchestrator._dispatcher  # noqa: SLF001
    register_workflow_adapters(
        dispatcher,
        spec,
        plugin_registry=plugin_registry,
    )
    # Override human:// scheme with scripted adapter
    dispatcher.register("human", scripted)

    try:
        summary = await orchestrator.run(spec)
    except Exception as exc:
        return {"error": str(exc), "code": "execution_error"}

    return {
        "run_id": summary.run_id,
        "status": summary.status,
        "completed_nodes": summary.completed_nodes,
        "failed_nodes": summary.failed_nodes,
        "total_cost": summary.total_cost,
    }


async def get_run_status(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,  # noqa: ARG001
    run_id: str,
) -> dict[str, Any]:
    """Return status dict for a run."""
    run = await exec_store.get_run(run_id)
    if run is None:
        return {"error": f"Run '{run_id}' not found", "code": "not_found"}
    return _run_to_status(run)


async def list_runs(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,  # noqa: ARG001
    limit: int = 10,
) -> dict[str, Any]:
    """List recent runs."""
    runs = await exec_store.list_runs(limit=limit)
    return {"runs": [_run_to_status(r) for r in runs]}


async def debug_node(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    run_id: str,
    node_id: str,
) -> dict[str, Any]:
    """Return debug info for a specific node in a run."""
    run = await exec_store.get_run(run_id)
    if run is None:
        return {"error": f"Run '{run_id}' not found", "code": "not_found"}

    record = await exec_store.get_step(run_id, node_id)
    if record is None:
        return {"error": f"Node '{node_id}' not found in run '{run_id}'", "code": "not_found"}

    all_artifacts = await art_store.list_by_run(run_id)
    art_by_id = {a.id: a for a in all_artifacts}

    inputs = [
        _artifact_dict(art_by_id[ref])
        for ref in record.input_artifact_refs
        if ref in art_by_id
    ]
    outputs = [
        _artifact_dict(art_by_id[ref])
        for ref in record.output_artifact_refs
        if ref in art_by_id
    ]

    # Cost for this node
    cost: float | None = None
    try:
        cost_summary = await exec_store.get_run_cost_summary(run_id)
        if cost_summary and cost_summary.node_costs:
            cost = cost_summary.node_costs.get(node_id)
    except Exception:  # noqa: BLE001
        pass

    return {
        "node_id": node_id,
        "agent_id": record.agent_id,
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "latency_ms": record.latency_ms,
        "inputs": inputs,
        "outputs": outputs,
        "prompt": _truncate(record.prompt, "") if record.prompt else None,
        "cost": cost,
        "error": record.error,
    }


async def diagnose_run(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    run_id: str,
) -> dict[str, Any]:
    """Diagnose a run, reusing ``trace/diagnose``."""
    run = await exec_store.get_run(run_id)
    if run is None:
        return {"error": f"Run '{run_id}' not found", "code": "not_found"}

    try:
        from binex.trace.diagnose import diagnose_run as _diagnose
        from binex.trace.diagnose import report_to_dict

        report = await _diagnose(run_id, exec_store, art_store)
        result = report_to_dict(report)
        # Truncate any long string values in the report
        _truncate_dict_strings(result)
        return result
    except Exception as exc:
        return {"error": str(exc), "code": "execution_error"}


async def diff_runs(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    run_id_a: str,
    run_id_b: str,
) -> dict[str, Any]:
    """Diff two runs, reusing ``trace/diff``."""
    for rid in (run_id_a, run_id_b):
        run = await exec_store.get_run(rid)
        if run is None:
            return {"error": f"Run '{rid}' not found", "code": "not_found"}

    try:
        from binex.trace.diff import diff_runs as _diff

        report = await _diff(run_id_a, run_id_b, exec_store, art_store)
        result = _diff_report_to_dict(report)
        _truncate_dict_strings(result)
        return result
    except Exception as exc:
        return {"error": str(exc), "code": "execution_error"}


async def replay_node(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    run_id: str,
    node_id: str,
    model: str | None = None,
    prompt: str | None = None,
) -> dict[str, Any]:
    """Replay a single node, with optional model and prompt overrides."""
    from binex.mcp_server.tools import _apply_node_prompt_override, _load_workflow_for_replay

    run = await exec_store.get_run(run_id)
    if run is None:
        return {"error": f"Run '{run_id}' not found", "code": "not_found"}

    # Feature gate: imported runs cannot be replayed
    if run.source and run.source.startswith("otel"):
        return {
            "error": (
                f"Run '{run_id}' was imported from an external trace and cannot be replayed. "
                "Replay requires a run that was executed natively by Binex."
            ),
            "code": "unsupported",
        }

    try:
        spec = await _load_workflow_for_replay(run, exec_store)
    except ValueError as exc:
        return {"error": str(exc), "code": "not_found"}

    # Apply prompt override on a copy of the spec
    if prompt is not None:
        try:
            spec = _apply_node_prompt_override(spec, node_id, prompt)
        except ValueError as exc:
            return {"error": str(exc), "code": "invalid_input"}

    agent_swaps: dict[str, str] = {}
    if model is not None:
        agent_swaps[node_id] = f"llm://{model}"

    try:
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.plugins import PluginRegistry
        from binex.runtime.replay import ReplayEngine

        plugin_registry = PluginRegistry()
        plugin_registry.discover()

        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
        )
        register_workflow_adapters(
            engine.dispatcher, spec, agent_swaps=agent_swaps,
            plugin_registry=plugin_registry,
        )

        summary = await engine.replay(
            original_run_id=run_id,
            workflow=spec,
            from_step=node_id,
            agent_swaps=agent_swaps,
        )
    except Exception as exc:
        return {"error": str(exc), "code": "execution_error"}

    # Collect output artifacts from the replayed node
    all_artifacts = await art_store.list_by_run(summary.run_id)
    all_records = await exec_store.list_records(summary.run_id)
    node_record = next((r for r in all_records if r.task_id == node_id), None)
    node_output: list[dict[str, Any]] = []
    if node_record:
        art_by_id = {a.id: a for a in all_artifacts}
        node_output = [
            _artifact_dict(art_by_id[ref])
            for ref in node_record.output_artifact_refs
            if ref in art_by_id
        ]

    return {
        "new_run_id": summary.run_id,
        "status": summary.status,
        "node_output": node_output,
    }


async def eval_run(
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
    suite_path: str,
) -> dict[str, Any]:
    """Run an eval suite and return results dict."""
    from pathlib import Path as _Path

    path = _Path(suite_path)
    if not path.exists():
        return {"error": f"Suite file '{suite_path}' not found", "code": "not_found"}

    try:
        from binex.eval.loader import load_suite
        from binex.eval.runner import run_suite

        suite = load_suite(str(path))
        result = await run_suite(
            suite,
            parallel=1,
            exec_store=exec_store,
            art_store=art_store,
        )
    except Exception as exc:
        return {"error": str(exc), "code": "execution_error"}

    return result.model_dump(mode="json")


async def get_artifact(
    exec_store: ExecutionStore,  # noqa: ARG001
    art_store: ArtifactStore,
    artifact_id: str,
) -> dict[str, Any]:
    """Return full (untruncated) artifact content."""
    art = await art_store.get(artifact_id)
    if art is None:
        return {"error": f"Artifact '{artifact_id}' not found", "code": "not_found"}

    content = art.content or ""
    if isinstance(content, (dict, list)):
        import json as _json
        content = _json.dumps(content, indent=2)

    return {
        "id": art.id,
        "run_id": art.run_id,
        "type": art.type,
        "content": str(content),  # full, not truncated
        "lineage": art.lineage.model_dump() if art.lineage else None,
    }


# ---------------------------------------------------------------------------
# Private serialisation helpers
# ---------------------------------------------------------------------------

def _truncate_dict_strings(obj: Any, *, depth: int = 0) -> None:
    """In-place: truncate all string values in a nested dict/list structure."""
    if depth > 10:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and len(v) > _TRUNCATE_AT:
                obj[k] = _truncate(v)
            else:
                _truncate_dict_strings(v, depth=depth + 1)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and len(item) > _TRUNCATE_AT:
                obj[i] = _truncate(item)
            else:
                _truncate_dict_strings(item, depth=depth + 1)


def _diff_report_to_dict(report: Any) -> dict[str, Any]:
    """Convert a DiffReport to a serialisable dict for MCP output."""
    try:
        # Prefer model_dump if available (Pydantic model)
        return report.model_dump(mode="json")
    except AttributeError:
        pass

    # Fallback: manual extraction of common DiffReport fields
    steps: list[dict[str, Any]] = []
    for step in getattr(report, "steps", []):
        try:
            steps.append(step.model_dump(mode="json"))
        except AttributeError:
            steps.append({"node_id": getattr(step, "node_id", None)})

    return {
        "summary": getattr(report, "summary", None),
        "steps": steps,
    }
