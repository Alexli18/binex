"""Resume engine — continue a failed/interrupted run from the point of failure.

Resume creates a new immutable child run linked to its parent via
``RunSummary.resumed_from``. Nodes that completed in the parent (and whose
definition is unchanged) are cached — their artifacts are reused so the budget
is not re-spent. Failed, timed-out, never-started, and orphaned-running nodes
are re-executed. See issue #54 for the full design.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import yaml  # type: ignore[import-untyped]

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.execution import RunSummary
from binex.models.task import TaskStatus
from binex.models.workflow import WorkflowSpec
from binex.runtime.back_edge import evaluate_when
from binex.runtime.budget import check_batch_budget, skip_all_remaining
from binex.runtime.replay import ReplayEngine, node_definition_changed

# Node statuses whose output can be reused (cached) on resume. Skipped nodes
# leave no execution record, so they fall through to re-run and are re-evaluated
# against their `when` condition in the resume loop.
_CACHEABLE = {TaskStatus.COMPLETED}
# Parent run statuses that require a warning before resuming (deliberate stop).
_INTENTIONAL_STOP = {"cancelled", "stopped"}


class ResumeError(Exception):
    """Raised when a run cannot be resumed."""


@dataclass
class ResumeResult:
    """Outcome of a resume: the child run summary plus any user-facing warnings."""

    summary: RunSummary
    resumed_nodes: int
    cached_nodes: int
    warnings: list[str] = field(default_factory=list)


def _drifted(node_id: str, spec: WorkflowSpec, parent_spec: WorkflowSpec) -> bool:
    """True if *node_id*'s definition differs from the parent run's snapshot.

    A node missing from either side counts as drifted — it was added or removed,
    so there is no cached result to trust.
    """
    current, stored = spec.nodes.get(node_id), parent_spec.nodes.get(node_id)
    if current is None or stored is None:
        return True
    return node_definition_changed(current, stored)


class ResumeEngine(ReplayEngine):
    """Resumes a failed/interrupted run, reusing cached artifacts of done nodes."""

    async def resume(
        self,
        run_id: str,
        *,
        from_node: str | None = None,
        force: bool = False,
    ) -> ResumeResult:
        """Resume a run into a new child run.

        Args:
            run_id: The parent run to resume.
            from_node: Force re-execution starting at this node and everything
                downstream (overrides the status/drift-based partition).
            force: Override topology-drift and running-status refusals.

        Raises:
            ResumeError: If the run cannot be resumed.
        """
        parent = await self.execution_store.get_run(run_id)
        if parent is None:
            raise ResumeError(f"Run '{run_id}' not found")

        warnings = self._check_resumable(parent, force=force)

        spec = self._load_parent_spec(parent)
        dag = DAG.from_workflow(spec)
        topo = dag.topological_order()

        parent_records = await self.execution_store.list_records(run_id)
        status_by_node = {r.task_id: r.status for r in parent_records}

        self._check_topology_drift(spec, status_by_node, force=force)

        cached = await self._compute_cached_set(
            parent, spec, dag, topo, status_by_node, from_node,
        )
        re_run = set(spec.nodes) - cached
        if not re_run:
            raise ResumeError(
                f"Run '{run_id}' has no failed or pending nodes to resume."
            )

        return await self._execute_resume(
            parent, spec, dag, topo, cached, re_run, warnings,
        )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _check_resumable(self, parent: RunSummary, *, force: bool) -> list[str]:
        """Validate the parent status; return warnings (raises if unresumable)."""
        status = parent.status
        if status == "completed":
            raise ResumeError(
                f"Run '{parent.run_id}' already completed — nothing to resume."
            )
        if status == "running" and not force:
            raise ResumeError(
                f"Run '{parent.run_id}' is still marked 'running'; it may be "
                "active in another process. Re-run with --force only if the "
                "process is confirmed dead."
            )
        if status in _INTENTIONAL_STOP:
            return [
                f"Run '{parent.run_id}' was {status}; resuming on explicit request."
            ]
        return []

    def _load_parent_spec(self, parent: RunSummary) -> WorkflowSpec:
        """Load the workflow spec from the parent's recorded path."""
        from binex.workflow_spec.loader import load_workflow

        if not parent.workflow_path:
            raise ResumeError(
                f"Run '{parent.run_id}' has no recorded workflow_path; "
                "cannot resume."
            )
        try:
            return load_workflow(parent.workflow_path)
        except FileNotFoundError as exc:
            raise ResumeError(
                f"Workflow file '{parent.workflow_path}' not found; "
                "cannot resume."
            ) from exc

    def _check_topology_drift(
        self,
        spec: WorkflowSpec,
        status_by_node: dict[str, TaskStatus],
        *,
        force: bool,
    ) -> None:
        """Refuse if nodes the parent executed no longer exist in the spec."""
        removed = sorted(nid for nid in status_by_node if nid not in spec.nodes)
        if removed and not force:
            raise ResumeError(
                "Workflow topology changed since the run "
                f"(missing nodes: {', '.join(removed)}). "
                "Re-run with --force to override."
            )

    # ------------------------------------------------------------------
    # Partitioning
    # ------------------------------------------------------------------

    async def _compute_cached_set(
        self,
        parent: RunSummary,
        spec: WorkflowSpec,
        dag: DAG,
        topo: list[str],
        status_by_node: dict[str, TaskStatus],
        from_node: str | None,
    ) -> set[str]:
        """Partition nodes into cached (reused) vs re-run, by status + drift."""
        parent_spec = await self.snapshot_spec(parent)

        cached: set[str] = set()
        for nid in topo:  # topological order → upstream decided before downstream
            if status_by_node.get(nid) not in _CACHEABLE:
                continue
            # Per-node drift: a changed definition must be re-run.
            if parent_spec is not None and _drifted(nid, spec, parent_spec):
                continue
            # A node can only be cached if its entire upstream is cached.
            if not dag.dependencies(nid).issubset(cached):
                continue
            cached.add(nid)

        # --from override: invalidate the node and everything downstream.
        if from_node is not None:
            if from_node not in spec.nodes:
                raise ResumeError(f"Node '{from_node}' not found in workflow")
            cached -= {from_node} | dag.descendants(from_node)

        return cached

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_resume(
        self,
        parent: RunSummary,
        spec: WorkflowSpec,
        dag: DAG,
        topo: list[str],
        cached: set[str],
        re_run: set[str],
        warnings: list[str],
    ) -> ResumeResult:
        """Create the child run, replay cached steps, and run the rest."""
        child_id = f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # Cumulative budget: parent.total_cost is already cumulative-to-parent.
        prior_cost = parent.total_cost

        workflow_yaml = yaml.dump(
            spec.model_dump(exclude={"source_path"}), sort_keys=True,
        )
        workflow_hash = await self.execution_store.store_workflow_snapshot(
            workflow_yaml, version=spec.version,
        )

        summary = RunSummary(
            run_id=child_id,
            workflow_name=spec.name,
            workflow_path=spec.source_path or parent.workflow_path,
            workflow_hash=workflow_hash,
            status="running",
            total_nodes=len(spec.nodes),
            resumed_from=parent.run_id,
        )
        await self.execution_store.create_run(summary)

        node_artifacts: dict[str, list[Artifact]] = {}
        await self._cache_upstream_steps(
            parent.run_id, child_id, trace_id, topo, cached, node_artifacts,
        )

        scheduler = Scheduler(dag)
        for nid in cached:
            scheduler.mark_completed(nid)

        accumulated_cost = prior_cost
        budget_exceeded = False
        while not scheduler.is_complete() and not scheduler.is_blocked():
            ready = [n for n in scheduler.ready_nodes() if n in re_run]
            if not ready:
                await asyncio.sleep(0.01)
                continue

            if check_batch_budget(spec, accumulated_cost) == "stop":
                budget_exceeded = True
                skip_all_remaining(scheduler, ready)
                break

            tasks = []
            for nid in ready:
                node_spec = spec.nodes[nid]
                if node_spec.when and not evaluate_when(node_spec.when, node_artifacts):
                    scheduler.mark_skipped(nid)
                    continue
                scheduler.mark_running(nid)
                tasks.append(
                    self._execute_node(
                        spec, dag, scheduler, child_id, trace_id,
                        nid, node_artifacts, {},
                    )
                )
            if tasks:
                await asyncio.gather(*tasks)

            cost_summary = await self.execution_store.get_run_cost_summary(child_id)
            accumulated_cost = prior_cost + cost_summary.total_cost

        summary.completed_at = datetime.now(UTC)
        summary.completed_nodes = len(scheduler.completed)
        summary.failed_nodes = len(scheduler.failed)
        summary.skipped_nodes = len(scheduler.skipped)
        summary.total_cost = accumulated_cost
        summary.status = self._final_status(budget_exceeded, scheduler)
        await self.execution_store.update_run(summary)

        return ResumeResult(
            summary=summary,
            resumed_nodes=len(re_run),
            cached_nodes=len(cached),
            warnings=warnings,
        )

    @staticmethod
    def _final_status(budget_exceeded: bool, scheduler: Scheduler) -> str:
        if budget_exceeded:
            return "over_budget"
        if scheduler.failed:
            return "failed"
        if scheduler.is_complete():
            return "completed"
        return "failed"
