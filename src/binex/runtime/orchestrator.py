"""Orchestrator — load workflow, build DAG, schedule, dispatch, collect results."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import click

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.dispatcher import Dispatcher, _backoff_delay
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore

logger = logging.getLogger(__name__)


def get_effective_policy(spec: WorkflowSpec) -> str:
    """Return the effective budget policy — from workflow or default 'stop'."""
    if spec.budget:
        return spec.budget.policy
    return "stop"


def get_node_max_cost(
    node: NodeSpec, spec: WorkflowSpec, accumulated_workflow_cost: float
) -> float | None:
    """Return effective max_cost for a node, considering workflow budget."""
    if node.budget is None:
        return None
    node_max = node.budget.max_cost
    if spec.budget:
        remaining = spec.budget.max_cost - accumulated_workflow_cost
        return min(node_max, remaining)
    return node_max


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
        accumulated_cost = 0.0
        budget_exceeded = False

        while not scheduler.is_complete() and not scheduler.is_blocked():
            ready = scheduler.ready_nodes()
            if not ready:
                await asyncio.sleep(0.01)
                continue

            # Budget check before scheduling next batch
            if spec.budget and spec.budget.max_cost > 0:
                if accumulated_cost > spec.budget.max_cost:
                    if spec.budget.policy == "stop":
                        budget_exceeded = True
                        for node_id in ready:
                            scheduler.mark_skipped(node_id)
                        # Skip all remaining ready nodes
                        while not scheduler.is_complete() and not scheduler.is_blocked():
                            remaining = scheduler.ready_nodes()
                            if not remaining:
                                break
                            for node_id in remaining:
                                scheduler.mark_skipped(node_id)
                        break
                    else:  # policy == "warn"
                        msg = (
                            f"Budget exceeded: ${accumulated_cost:.2f} / "
                            f"${spec.budget.max_cost:.2f} (policy: warn, continuing)"
                        )
                        logger.warning(msg)
                        click.echo(f"\u26a0 {msg}", err=True)

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
                        node_id, node_artifacts, accumulated_cost,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)

            # Update accumulated cost from store
            cost_summary = await self.execution_store.get_run_cost_summary(run_id)
            accumulated_cost = cost_summary.total_cost

        summary.completed_at = datetime.now(UTC)
        summary.completed_nodes = len(scheduler._completed)
        summary.failed_nodes = len(scheduler._failed)
        summary.skipped_nodes = len(scheduler._skipped)
        summary.total_cost = accumulated_cost
        if budget_exceeded:
            summary.status = "over_budget"
        elif scheduler._failed:
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
        accumulated_cost: float = 0.0,
    ) -> None:
        node_spec = spec.nodes[node_id]
        retry_policy = node_spec.retry_policy or (
            spec.defaults.retry_policy if spec.defaults else None
        )
        has_node_budget = node_spec.budget is not None
        node_max = get_node_max_cost(node_spec, spec, accumulated_cost)

        # When node has a budget, orchestrator handles retry (for pre-check).
        # Otherwise, dispatcher handles retry as before.
        if has_node_budget:
            max_retries = retry_policy.max_retries if retry_policy else 1
            task_retry_policy = None  # orchestrator handles retry
        else:
            max_retries = 1  # single attempt here, dispatcher handles retry
            task_retry_policy = retry_policy

        task = TaskNode(
            id=f"{run_id}_{node_id}",
            run_id=run_id,
            node_id=node_id,
            agent=node_spec.agent,
            system_prompt=node_spec.system_prompt,
            tools=node_spec.tools,
            inputs=node_spec.inputs,
            retry_policy=task_retry_policy,
            deadline_ms=node_spec.deadline_ms or (
                spec.defaults.deadline_ms if spec.defaults else None
            ),
            config=node_spec.config,
        )

        input_artifacts: list[Artifact] = []
        for dep_id in dag.dependencies(node_id):
            input_artifacts.extend(node_artifacts.get(dep_id, []))

        start_ms = _now_ms()
        error_msg: str | None = None
        output_artifacts: list[Artifact] = []
        succeeded = False

        for attempt in range(1, max_retries + 1):
            # --- Per-node budget pre-check (before retry, not first attempt) ---
            if attempt > 1 and node_max is not None:
                all_costs = await self.execution_store.list_costs(run_id)
                node_cost = sum(r.cost for r in all_costs if r.task_id == node_id)
                remaining = node_max - node_cost

                if remaining <= 0:
                    policy = get_effective_policy(spec)
                    if policy == "stop":
                        error_msg = (
                            f"Node '{node_id}': budget exhausted "
                            f"(${node_cost:.2f}/${node_max:.2f}), skipping retry"
                        )
                        logger.warning(error_msg)
                        click.echo(f"\u26a0 {error_msg}", err=True)
                        break
                    else:  # warn — interactive prompt
                        proceed = click.confirm(
                            f"\u26a0 Node '{node_id}' retry will likely exceed budget "
                            f"(${remaining:.2f} remaining of ${node_max:.2f}). "
                            f"Continue?",
                            default=False,
                        )
                        if not proceed:
                            error_msg = (
                                f"Node '{node_id}': retry cancelled by user (budget)"
                            )
                            break

            try:
                result = await self.dispatcher.dispatch(
                    task, input_artifacts, trace_id,
                )
                output_artifacts = result.artifacts

                # Record cost if present
                if result.cost:
                    if node_max is not None:
                        result.cost.node_budget = node_max
                    await self.execution_store.record_cost(result.cost)

                # --- Per-node budget post-check ---
                if node_max is not None and result.cost:
                    all_costs = await self.execution_store.list_costs(run_id)
                    node_cost = sum(
                        r.cost for r in all_costs if r.task_id == node_id
                    )
                    if node_cost > node_max:
                        policy = get_effective_policy(spec)
                        if policy == "stop":
                            error_msg = (
                                f"Node '{node_id}': exceeded budget "
                                f"${node_cost:.2f} / ${node_max:.2f}"
                            )
                            logger.warning(error_msg)
                            click.echo(f"\u26a0 {error_msg}", err=True)
                            break  # don't store artifacts
                        else:  # warn
                            msg = (
                                f"Node '{node_id}': exceeded budget "
                                f"${node_cost:.2f} / ${node_max:.2f} "
                                f"(policy: warn, keeping result)"
                            )
                            logger.warning(msg)
                            click.echo(f"\u26a0 {msg}", err=True)

                # Success — store artifacts
                for art in output_artifacts:
                    await self.artifact_store.store(art)
                node_artifacts[node_id] = output_artifacts
                succeeded = True
                error_msg = None
                break  # exit retry loop on success

            except Exception as exc:
                error_msg = str(exc)
                if attempt < max_retries:
                    backoff = (
                        retry_policy.backoff if retry_policy else "exponential"
                    )
                    delay = _backoff_delay(attempt, backoff)
                    await asyncio.sleep(delay)

        if succeeded:
            scheduler.mark_completed(node_id)
            status = task.status.__class__("completed")
        else:
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
