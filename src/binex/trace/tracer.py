"""Timeline trace generation for workflow runs."""

from __future__ import annotations

from typing import Any

from binex.stores.execution_store import ExecutionStore


async def generate_timeline(store: ExecutionStore, run_id: str) -> str:
    """Generate a human-readable timeline for a run."""
    records = await store.list_records(run_id)
    if not records:
        return "No records found for this run."

    records.sort(key=lambda r: r.timestamp)

    lines: list[str] = []
    run = await store.get_run(run_id)
    if run:
        lines.append(f"Run: {run.run_id} ({run.workflow_name})")
        lines.append(f"Status: {run.status}")
        lines.append(f"Started: {run.started_at}")
        if run.completed_at:
            lines.append(f"Completed: {run.completed_at}")
        lines.append("")

    for rec in records:
        status = rec.status.value
        agent = rec.agent_id
        line = f"  [{status:>9}] {rec.task_id:<20} agent={agent}  latency={rec.latency_ms}ms"
        lines.append(line)

        if rec.input_artifact_refs:
            lines.append(f"             inputs:  {', '.join(rec.input_artifact_refs)}")
        if rec.output_artifact_refs:
            lines.append(f"             outputs: {', '.join(rec.output_artifact_refs)}")
        if rec.error:
            lines.append(f"             error:   {rec.error}")

    return "\n".join(lines)


async def generate_timeline_json(store: ExecutionStore, run_id: str) -> list[dict[str, Any]]:
    """Generate timeline data as a list of dicts for JSON output."""
    records = await store.list_records(run_id)
    records.sort(key=lambda r: r.timestamp)

    return [
        {
            "task_id": rec.task_id,
            "agent_id": rec.agent_id,
            "status": rec.status.value,
            "latency_ms": rec.latency_ms,
            "timestamp": rec.timestamp.isoformat(),
            "input_artifact_refs": rec.input_artifact_refs,
            "output_artifact_refs": rec.output_artifact_refs,
            "error": rec.error,
        }
        for rec in records
    ]
