"""Replay engine — create new run from existing, reusing cached upstream artifacts."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskNode, TaskStatus
from binex.models.workflow import WorkflowSpec
from binex.runtime.dispatcher import Dispatcher
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore


class ReplayEngine:
    """Replays a run from a specific step, reusing cached upstream artifacts."""

    def __init__(
        self,
        execution_store: ExecutionStore,
        artifact_store: ArtifactStore,
        dispatcher: Dispatcher | None = None,
    ) -> None:
        self.execution_store = execution_store
        self.artifact_store = artifact_store
        self.dispatcher = dispatcher or Dispatcher()

    async def _cache_upstream_steps(
        self,
        original_run_id: str,
        run_id: str,
        trace_id: str,
        topo_order: list[str],
        cached_steps: set[str],
        node_artifacts: dict[str, list[Artifact]],
    ) -> None:
        """Copy execution records and artifacts from the original run for cached steps."""
        original_records = await self.execution_store.list_records(original_run_id)
        original_by_task: dict[str, ExecutionRecord] = {
            r.task_id: r for r in original_records
        }

        for step in topo_order:
            if step not in cached_steps:
                continue

            orig_rec = original_by_task.get(step)
            if orig_rec is None:
                continue

            cached_artifacts: list[Artifact] = []
            for art_id in orig_rec.output_artifact_refs:
                art = await self.artifact_store.get(art_id)
                if art is not None:
                    cached_artifacts.append(art)

            node_artifacts[step] = cached_artifacts

            cached_record = ExecutionRecord(
                id=f"rec_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                task_id=step,
                agent_id=orig_rec.agent_id,
                status=TaskStatus.COMPLETED,
                input_artifact_refs=orig_rec.input_artifact_refs,
                output_artifact_refs=orig_rec.output_artifact_refs,
                latency_ms=0,
                trace_id=trace_id,
            )
            await self.execution_store.record(cached_record)

    async def replay(
        self,
        original_run_id: str,
        workflow: dict[str, Any] | WorkflowSpec,
        from_step: str,
        agent_swaps: dict[str, str] | None = None,
    ) -> RunSummary:
        """Create a new immutable run, caching steps before from_step."""
        original_run = await self.execution_store.get_run(original_run_id)
        if original_run is None:
            raise ValueError(f"Run '{original_run_id}' not found")

        if isinstance(workflow, dict):
            spec = WorkflowSpec(**workflow)
        else:
            spec = workflow

        if from_step not in spec.nodes:
            raise ValueError(f"Step '{from_step}' not found in workflow")

        dag = DAG.from_workflow(spec)
        topo_order = dag.topological_order()

        from_index = topo_order.index(from_step)
        cached_steps = set(topo_order[:from_index])
        re_execute_steps = set(topo_order[from_index:])
        agent_swaps = agent_swaps or {}

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        summary = RunSummary(
            run_id=run_id,
            workflow_name=spec.name,
            workflow_path=spec.source_path,
            status="running",
            total_nodes=len(spec.nodes),
            forked_from=original_run_id,
            forked_at_step=from_step,
        )
        await self.execution_store.create_run(summary)

        node_artifacts: dict[str, list[Artifact]] = {}

        # Phase 1: Cache upstream steps from original run
        await self._cache_upstream_steps(
            original_run_id, run_id, trace_id,
            topo_order, cached_steps, node_artifacts,
        )

        # Phase 2: Re-execute from from_step onward
        scheduler = Scheduler(dag)
        for step in cached_steps:
            scheduler.mark_completed(step)

        while not scheduler.is_complete() and not scheduler.is_blocked():
            ready = scheduler.ready_nodes()
            if not ready:
                await asyncio.sleep(0.01)
                continue

            tasks = []
            for node_id in ready:
                if node_id not in re_execute_steps:
                    continue
                scheduler.mark_running(node_id)
                tasks.append(
                    self._execute_node(
                        spec, dag, scheduler, run_id, trace_id,
                        node_id, node_artifacts, agent_swaps,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)

        # Finalize
        summary.completed_at = datetime.now(UTC)
        if scheduler.is_complete():
            summary.status = "completed"
            summary.completed_nodes = len(spec.nodes)
        else:
            summary.status = "failed"
            summary.completed_nodes = len(cached_steps) + len(
                [n for n in re_execute_steps if n in scheduler._completed]
            )
            summary.failed_nodes = len(
                [n for n in re_execute_steps if n in scheduler._failed]
            )

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
        agent_swaps: dict[str, str],
    ) -> None:
        node_spec = spec.nodes[node_id]
        agent = agent_swaps.get(node_id, node_spec.agent)

        task = TaskNode(
            id=f"{run_id}_{node_id}",
            run_id=run_id,
            node_id=node_id,
            agent=agent,
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

        input_artifacts: list[Artifact] = []
        for dep_id in dag.dependencies(node_id):
            input_artifacts.extend(node_artifacts.get(dep_id, []))

        start_ms = int(time.monotonic() * 1000)
        error_msg: str | None = None
        output_artifacts: list[Artifact] = []

        try:
            result = await self.dispatcher.dispatch(
                task, input_artifacts, trace_id,
            )
            output_artifacts = result.artifacts
            for art in output_artifacts:
                await self.artifact_store.store(art)
            node_artifacts[node_id] = output_artifacts
            scheduler.mark_completed(node_id)
            status = TaskStatus.COMPLETED

            # Record cost if present
            if result.cost:
                await self.execution_store.record_cost(result.cost)
        except Exception as exc:
            error_msg = str(exc)
            scheduler.mark_failed(node_id)
            status = TaskStatus.FAILED

        latency_ms = int(time.monotonic() * 1000) - start_ms
        record = ExecutionRecord(
            id=f"rec_{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            task_id=node_id,
            agent_id=agent,
            status=status,
            input_artifact_refs=[a.id for a in input_artifacts],
            output_artifact_refs=[a.id for a in output_artifacts],
            latency_ms=latency_ms,
            trace_id=trace_id,
            error=error_msg,
        )
        await self.execution_store.record(record)
