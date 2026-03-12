"""Shared node execution helpers for orchestrator and replay."""

from __future__ import annotations

import time
import uuid

from binex.graph.dag import DAG
from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord
from binex.stores.execution_store import ExecutionStore


def now_ms() -> int:
    """Current monotonic time in milliseconds."""
    return int(time.monotonic() * 1000)


def collect_input_artifacts(
    dag: DAG,
    node_id: str,
    node_artifacts: dict[str, list[Artifact]],
    extra: list[Artifact] | None = None,
) -> list[Artifact]:
    """Collect input artifacts from upstream dependencies."""
    inputs: list[Artifact] = []
    for dep_id in dag.dependencies(node_id):
        inputs.extend(node_artifacts.get(dep_id, []))
    if extra:
        inputs.extend(extra)
    return inputs


async def record_execution(
    execution_store: ExecutionStore,
    *,
    run_id: str,
    node_id: str,
    agent_id: str,
    status,
    input_artifacts: list[Artifact],
    output_artifacts: list[Artifact],
    latency_ms: int,
    trace_id: str,
    error: str | None,
) -> None:
    """Create and store an ExecutionRecord."""
    record = ExecutionRecord(
        id=f"rec_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        task_id=node_id,
        agent_id=agent_id,
        status=status,
        input_artifact_refs=[a.id for a in input_artifacts],
        output_artifact_refs=[a.id for a in output_artifacts],
        latency_ms=latency_ms,
        trace_id=trace_id,
        error=error,
    )
    await execution_store.record(record)
