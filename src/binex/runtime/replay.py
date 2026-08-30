"""Replay engine — create new run from existing, reusing cached upstream artifacts."""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import UTC, datetime
from typing import Any

import yaml  # type: ignore[import-untyped]

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskNode, TaskStatus
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime._node_executor import collect_input_artifacts, now_ms, record_execution
from binex.runtime.dispatcher import Dispatcher
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore


class ImportedRunError(ValueError):
    """Raised when an operation is not supported for OTel-imported runs."""


class WorkflowDriftError(ValueError):
    """Raised when a node replay would cache has changed since the original run.

    Replay reuses every node before ``from_step`` verbatim. If one of those node
    definitions was edited in the workflow file since the original run, its
    cached artifact is stale relative to the file — the replay would silently mix
    old outputs with a new workflow. Callers that accept that pass ``allow_drift``.
    """

    def __init__(self, drifted: list[str], original_run_id: str) -> None:
        self.drifted = drifted
        self.original_run_id = original_run_id
        names = ", ".join(f"'{n}'" for n in drifted)
        plural = "s" if len(drifted) > 1 else ""
        super().__init__(
            f"Cached upstream node{plural} {names} changed since run "
            f"'{original_run_id}' (agent, prompt, inputs, config, tools, or "
            f"dependencies). The cached output is stale relative to the workflow "
            f"file. Replay from an earlier step to re-execute the changed "
            f"node{plural}, or pass --allow-drift to reuse the cached output "
            f"knowingly."
        )


# ``${user.x}`` placeholders are substituted at load time, so a stored snapshot
# holds the resolved value while the workflow file still holds the template.
_USER_VAR_RE = re.compile(r"\$\{user\.[^}]*\}")


def _comparable_inputs(
    current: dict[str, Any], stored: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Drop input keys the current spec binds from a ``${user.*}`` variable.

    Those keys hold a template in the workflow file and the substituted value in
    a stored snapshot — comparing them would report drift for every run that
    used ``--var``. The binding is a run parameter, not a node definition, and
    replay does not re-supply variables, so it is excluded from the comparison.
    Every other key (literals, ``${node.*}`` references) is compared normally.
    """
    unbound = {
        key for key, value in current.items()
        if isinstance(value, str) and _USER_VAR_RE.search(value)
    }
    return (
        {k: v for k, v in current.items() if k not in unbound},
        {k: v for k, v in stored.items() if k not in unbound},
    )


def node_definition_changed(current: NodeSpec, stored: NodeSpec) -> bool:
    """True if *current* differs from the *stored* (snapshotted) definition.

    Compares the fields that determine a node's output, tolerating only the
    load-time ``${user.*}`` substitution described in :func:`_comparable_inputs`.
    """
    if (
        current.agent != stored.agent
        or current.system_prompt != stored.system_prompt
        or current.config != stored.config
        or current.tools != stored.tools
        or sorted(current.depends_on) != sorted(stored.depends_on)
    ):
        return True
    cur_inputs, stored_inputs = _comparable_inputs(current.inputs, stored.inputs)
    return cur_inputs != stored_inputs


def ensure_replayable(run: RunSummary, operation: str = "replay") -> None:
    """Raise ``ImportedRunError`` if *run* was imported from an external trace.

    This is the single gate applied by all replay/bisect paths (CLI, REST,
    MCP) so the check is never accidentally omitted.

    Args:
        run: The run summary to check.
        operation: Human-readable operation name used in the error message.

    Raises:
        ImportedRunError: When ``run.source`` indicates an imported run.
    """
    if run.source and run.source.startswith("otel"):
        raise ImportedRunError(
            f"Run '{run.run_id}' was imported from an external trace and cannot be "
            f"used for {operation}. "
            "Replay and bisect require runs that were executed natively by Binex."
        )


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

        # Batch-fetch all artifacts for the original run to avoid N+1 queries
        all_artifacts = await self.artifact_store.list_by_run(original_run_id)
        artifacts_by_id: dict[str, Artifact] = {a.id: a for a in all_artifacts}

        for step in topo_order:
            if step not in cached_steps:
                continue

            orig_rec = original_by_task.get(step)
            if orig_rec is None:
                continue

            cached_artifacts: list[Artifact] = [
                artifacts_by_id[art_id]
                for art_id in orig_rec.output_artifact_refs
                if art_id in artifacts_by_id
            ]

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

    async def snapshot_spec(self, run: RunSummary) -> WorkflowSpec | None:
        """The workflow spec *run* was executed with, or None if unavailable.

        None means "cannot verify" — runs recorded before snapshots existed, or
        a snapshot that no longer parses. Drift checking is skipped rather than
        turned into a hard failure for those.
        """
        if not run.workflow_hash:
            return None
        snapshot = await self.execution_store.get_workflow_snapshot(
            run.workflow_hash,
        )
        if not snapshot or "content" not in snapshot:
            return None
        try:
            return WorkflowSpec(**yaml.safe_load(snapshot["content"]))
        except Exception:
            return None

    async def _check_upstream_drift(
        self,
        original_run: RunSummary,
        spec: WorkflowSpec,
        cached_steps: set[str],
    ) -> None:
        """Raise WorkflowDriftError if any node replay would cache has changed.

        Only *cached* nodes are checked: nodes at or after ``from_step`` are
        re-executed, so changing them is the point of replaying.
        """
        original_spec = await self.snapshot_spec(original_run)
        if original_spec is None:
            return

        drifted = [
            nid for nid in sorted(cached_steps)
            if nid in spec.nodes and nid in original_spec.nodes
            and node_definition_changed(spec.nodes[nid], original_spec.nodes[nid])
        ]
        if drifted:
            raise WorkflowDriftError(drifted, original_run.run_id)

    async def _validate_replay_params(
        self,
        original_run_id: str,
        workflow: dict[str, Any] | WorkflowSpec,
        from_step: str,
        allow_drift: bool = False,
    ) -> tuple[WorkflowSpec, DAG, list[str], set[str], set[str]]:
        """Validate replay parameters and compute step partitions.

        Returns (spec, dag, topo_order, cached_steps, re_execute_steps).
        Raises ValueError if the original run or from_step is not found, and
        WorkflowDriftError if a cached node's definition changed (unless
        *allow_drift*).
        """
        original_run = await self.execution_store.get_run(original_run_id)
        if original_run is None:
            raise ValueError(f"Run '{original_run_id}' not found")

        ensure_replayable(original_run)

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

        if not allow_drift:
            await self._check_upstream_drift(original_run, spec, cached_steps)

        return spec, dag, topo_order, cached_steps, re_execute_steps

    def _determine_final_status(
        self,
        scheduler: Scheduler,
        re_execute_steps: set[str],
        cached_steps: set[str],
        total_nodes: int,
    ) -> tuple[str, int, int]:
        """Determine final run status from scheduler state.

        Returns (status, completed_nodes, failed_nodes).
        """
        if scheduler.is_complete():
            return "completed", total_nodes, 0

        completed_nodes = len(cached_steps) + len(
            [n for n in re_execute_steps if n in scheduler.completed]
        )
        failed_nodes = len(
            [n for n in re_execute_steps if n in scheduler.failed]
        )
        return "failed", completed_nodes, failed_nodes

    async def replay(
        self,
        original_run_id: str,
        workflow: dict[str, Any] | WorkflowSpec,
        from_step: str,
        agent_swaps: dict[str, str] | None = None,
        allow_drift: bool = False,
    ) -> RunSummary:
        """Create a new immutable run, caching steps before from_step."""
        spec, dag, topo_order, cached_steps, re_execute_steps = (
            await self._validate_replay_params(
                original_run_id, workflow, from_step, allow_drift=allow_drift,
            )
        )
        agent_swaps = agent_swaps or {}

        run_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # Snapshot the workflow so this replay is itself drift-checkable later.
        workflow_hash = await self.execution_store.store_workflow_snapshot(
            yaml.dump(spec.model_dump(exclude={"source_path"}), sort_keys=True),
            version=spec.version,
        )

        summary = RunSummary(
            run_id=run_id,
            workflow_name=spec.name,
            workflow_path=spec.source_path,
            workflow_hash=workflow_hash,
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
        status, completed_nodes, failed_nodes = self._determine_final_status(
            scheduler, re_execute_steps, cached_steps, len(spec.nodes),
        )
        summary.status = status
        summary.completed_nodes = completed_nodes
        summary.failed_nodes = failed_nodes

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

        input_artifacts = collect_input_artifacts(dag, node_id, node_artifacts)

        start_ms = now_ms()
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

        latency_ms = now_ms() - start_ms
        await record_execution(
            self.execution_store,
            run_id=run_id,
            node_id=node_id,
            agent_id=agent,
            status=status,
            input_artifacts=input_artifacts,
            output_artifacts=output_artifacts,
            latency_ms=latency_ms,
            trace_id=trace_id,
            error=error_msg,
        )
