"""Orchestrator — load workflow, build DAG, schedule, dispatch, collect results."""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskNode
from binex.models.workflow import WorkflowSpec
from binex.runtime.dispatcher import Dispatcher
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore


class Orchestrator:
    """Runs a workflow: parse -> DAG -> schedule -> dispatch -> collect."""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        execution_store: ExecutionStore,
    ) -> None:
        self.artifact_store = artifact_store
        self.execution_store = execution_store
        self.dispatcher = Dispatcher()

    async def run_workflow(
        self,
        workflow: dict[str, Any] | WorkflowSpec,
        *,
        user_vars: dict[str, str] | None = None,
    ) -> RunSummary:
        if isinstance(workflow, dict):
            spec = WorkflowSpec(**workflow)
        else:
            spec = workflow

        dag = DAG.from_workflow(spec)
        scheduler = Scheduler(dag)
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        summary = RunSummary(
            run_id=run_id,
            workflow_name=spec.name,
            status="running",
            total_nodes=len(spec.nodes),
        )
        await self.execution_store.create_run(summary)

        # node_id -> list of output artifacts
        node_artifacts: dict[str, list[Artifact]] = {}

        while not scheduler.is_complete() and not scheduler.is_blocked():
            ready = scheduler.ready_nodes()
            if not ready:
                await asyncio.sleep(0.01)
                continue

            tasks = []
            for node_id in ready:
                node_spec = spec.nodes[node_id]
                # Evaluate when condition if present
                if node_spec.when:
                    condition_met = evaluate_when(node_spec.when, node_artifacts)
                    if not condition_met:
                        scheduler.mark_skipped(node_id)
                        continue

                scheduler.mark_running(node_id)
                tasks.append(
                    self._execute_node(
                        spec, dag, scheduler, run_id, trace_id,
                        node_id, node_artifacts,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)

        summary.completed_at = datetime.now(UTC)
        summary.completed_nodes = len(scheduler._completed)
        summary.failed_nodes = len(scheduler._failed)
        summary.skipped_nodes = len(scheduler._skipped)
        if scheduler._failed:
            summary.status = "failed"
        elif scheduler.is_complete():
            summary.status = "completed"
        else:
            summary.status = "failed"

        await self.execution_store.update_run(summary)
        return summary

    async def _execute_node(
        self,
        spec: WorkflowSpec,
        dag: DAG,
        scheduler: Scheduler,
        run_id: str,
        trace_id: str,
        node_id: str,
        node_artifacts: dict[str, list[Artifact]],
    ) -> None:
        node_spec = spec.nodes[node_id]
        task = TaskNode(
            id=f"{run_id}_{node_id}",
            run_id=run_id,
            node_id=node_id,
            agent=node_spec.agent,
            system_prompt=node_spec.system_prompt,
            tools=node_spec.tools,
            inputs=node_spec.inputs,
            retry_policy=node_spec.retry_policy or (
                spec.defaults.retry_policy if spec.defaults else None
            ),
            deadline_ms=node_spec.deadline_ms or (
                spec.defaults.deadline_ms if spec.defaults else None
            ),
            config=node_spec.config,
        )

        # Gather input artifacts from upstream nodes
        input_artifacts: list[Artifact] = []
        for dep_id in dag.dependencies(node_id):
            input_artifacts.extend(node_artifacts.get(dep_id, []))

        start_ms = _now_ms()
        error_msg: str | None = None
        output_artifacts: list[Artifact] = []

        try:
            output_artifacts = await self.dispatcher.dispatch(
                task, input_artifacts, trace_id,
            )
            for art in output_artifacts:
                await self.artifact_store.store(art)
            node_artifacts[node_id] = output_artifacts
            scheduler.mark_completed(node_id)
            status = task.status.__class__("completed")
        except Exception as exc:
            error_msg = str(exc)
            scheduler.mark_failed(node_id)
            status = task.status.__class__("failed")

        latency_ms = _now_ms() - start_ms
        record = ExecutionRecord(
            id=f"rec_{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            task_id=node_id,
            agent_id=node_spec.agent,
            status=status,
            input_artifact_refs=[a.id for a in input_artifacts],
            output_artifact_refs=[a.id for a in output_artifacts],
            latency_ms=latency_ms,
            trace_id=trace_id,
            error=error_msg,
        )
        await self.execution_store.record(record)


_WHEN_RE = re.compile(r"^\$\{(\w+)\.(\w+)\}\s*(==|!=)\s*(.+)$")


def evaluate_when(when_str: str, node_artifacts: dict[str, list[Artifact]]) -> bool:
    """Evaluate a when-condition string against collected node artifacts.

    Returns True if the condition is satisfied, False otherwise.
    Raises ValueError for malformed when strings.
    """
    m = _WHEN_RE.match(when_str.strip())
    if not m:
        raise ValueError(f"Invalid when condition syntax: {when_str!r}")

    node_id, output_name, operator, value = m.group(1), m.group(2), m.group(3), m.group(4).strip()

    artifacts = node_artifacts.get(node_id)
    if not artifacts:
        return False

    # Match artifact by type (output_name), fall back to first artifact
    matching = [a for a in artifacts if a.type == output_name]
    actual = str(matching[0].content) if matching else str(artifacts[0].content)

    if operator == "==":
        return actual == value
    else:  # !=
        return actual != value


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
