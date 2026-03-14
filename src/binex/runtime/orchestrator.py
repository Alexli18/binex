"""Orchestrator — load workflow, build DAG, schedule, dispatch, collect results."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import click
import yaml

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.execution import RunSummary
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime._node_executor import collect_input_artifacts, now_ms, record_execution
from binex.runtime.back_edge import evaluate_back_edge, evaluate_when
from binex.runtime.budget import (
    check_batch_budget,
    get_effective_policy,
    get_node_max_cost,
    skip_all_remaining,
)
from binex.runtime.dispatcher import Dispatcher, _backoff_delay
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore
from binex.telemetry import get_tracer
from binex.webhook import WebhookSender

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs a workflow: parse -> DAG -> schedule -> dispatch -> collect."""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        execution_store: ExecutionStore,
        *,
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
        event_callback: Callable[[dict], Any] | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.execution_store = execution_store
        self.dispatcher = Dispatcher()
        self._pending_feedback: dict[str, list[Artifact]] = {}
        self._stream = stream
        self._stream_callback = stream_callback
        self._event_callback = event_callback

    async def _emit_event(self, event: dict) -> None:
        """Emit a lifecycle event if a callback is configured."""
        if self._event_callback is not None:
            result = self._event_callback(event)
            if asyncio.iscoroutine(result):
                await result

    async def run_workflow(
        self,
        workflow: dict[str, Any] | WorkflowSpec,
        *,
        user_vars: dict[str, str] | None = None,
        run_id: str | None = None,
    ) -> RunSummary:
        if isinstance(workflow, dict):
            spec = WorkflowSpec(**workflow)
        else:
            spec = workflow

        tracer = get_tracer()
        with tracer.start_as_current_span("binex.run") as span:
            span.set_attribute("workflow.name", spec.name)
            return await self._run_workflow_inner(spec, span, run_id=run_id)

    async def _run_workflow_inner(
        self,
        spec: WorkflowSpec,
        span: Any,
        *,
        run_id: str | None = None,
    ) -> RunSummary:
        dag = DAG.from_workflow(spec)
        scheduler = Scheduler(dag)
        run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # Store workflow snapshot
        workflow_yaml = yaml.dump(
            spec.model_dump(exclude={"source_path"}), sort_keys=True,
        )
        if hasattr(self.execution_store, "store_workflow_snapshot"):
            workflow_hash = await self.execution_store.store_workflow_snapshot(
                workflow_yaml, version=spec.version,
            )
        else:
            workflow_hash = hashlib.sha256(workflow_yaml.encode()).hexdigest()

        summary = RunSummary(
            run_id=run_id,
            workflow_name=spec.name,
            workflow_path=spec.source_path,
            workflow_hash=workflow_hash,
            status="running",
            total_nodes=len(spec.nodes),
        )
        await self.execution_store.create_run(summary)

        # node_id -> list of output artifacts
        node_artifacts: dict[str, list[Artifact]] = {}
        node_artifacts_history: dict[str, list[list[Artifact]]] = {}
        accumulated_cost = 0.0
        budget_exceeded = False

        while not scheduler.is_complete() and not scheduler.is_blocked():
            ready = scheduler.ready_nodes()
            if not ready:
                await asyncio.sleep(0.01)
                continue

            # Budget check before scheduling next batch
            budget_action = check_batch_budget(spec, accumulated_cost)
            if budget_action == "stop":
                budget_exceeded = True
                skip_all_remaining(scheduler, ready)
                break
            if budget_action == "warn":
                msg = (
                    f"Budget exceeded: ${accumulated_cost:.2f} / "
                    f"${spec.budget.max_cost:.2f} (policy: warn, continuing)"
                )
                logger.warning(msg)
                click.echo(f"\u26a0 {msg}", err=True)

            tasks = self._schedule_ready_nodes(
                spec, dag, scheduler, run_id, trace_id,
                ready, node_artifacts, accumulated_cost,
                node_artifacts_history,
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
        summary.status = self._determine_final_status(
            budget_exceeded, scheduler,
        )

        span.set_attribute("run.id", summary.run_id)
        span.set_attribute("run.status", summary.status)
        span.set_attribute("run.total_cost", summary.total_cost)
        span.set_attribute("run.node_count", summary.total_nodes)

        await self.execution_store.update_run(summary)

        # Fire webhook if configured
        webhook_url = (
            spec.webhook.url if spec.webhook
            else os.environ.get("BINEX_WEBHOOK_URL")
        )
        sender = WebhookSender.from_config(url=webhook_url)
        if sender is not None:
            await self._fire_webhook(sender, spec, summary)

        return summary

    def _schedule_ready_nodes(
        self,
        spec: WorkflowSpec,
        dag: DAG,
        scheduler: Scheduler,
        run_id: str,
        trace_id: str,
        ready: list[str],
        node_artifacts: dict[str, list[Artifact]],
        accumulated_cost: float,
        node_artifacts_history: dict[str, list[list[Artifact]]] | None = None,
    ) -> list:
        """Evaluate when-conditions and schedule ready nodes for execution."""
        if node_artifacts_history is None:
            node_artifacts_history = {}
        tasks = []
        for node_id in ready:
            node_spec = spec.nodes[node_id]
            if node_spec.when:
                if not evaluate_when(node_spec.when, node_artifacts):
                    scheduler.mark_skipped(node_id)
                    continue

            scheduler.mark_running(node_id)
            tasks.append(
                self._execute_node(
                    spec, dag, scheduler, run_id, trace_id,
                    node_id, node_artifacts, accumulated_cost,
                    node_artifacts_history,
                )
            )
        return tasks

    @staticmethod
    def _determine_final_status(
        budget_exceeded: bool, scheduler: Scheduler,
    ) -> str:
        """Determine the final run status."""
        if budget_exceeded:
            return "over_budget"
        if scheduler._failed:
            return "failed"
        if scheduler.is_complete():
            return "completed"
        return "failed"

    @staticmethod
    async def _fire_webhook(
        sender: WebhookSender,
        spec: WorkflowSpec,
        summary: RunSummary,
    ) -> None:
        """Send webhook notification for run lifecycle event."""
        event_map = {
            "completed": "run.completed",
            "failed": "run.failed",
            "over_budget": "run.budget_exceeded",
        }
        event = event_map.get(summary.status)
        if event is None:
            return

        data: dict[str, Any] = {
            "status": summary.status,
            "total_cost": summary.total_cost,
            "total_nodes": summary.total_nodes,
            "completed_nodes": summary.completed_nodes,
            "failed_nodes": summary.failed_nodes,
            "skipped_nodes": summary.skipped_nodes,
        }
        if summary.status == "over_budget" and spec.budget:
            data["max_cost"] = spec.budget.max_cost

        payload = {
            "event": event,
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": summary.run_id,
            "workflow_name": spec.name,
            "data": data,
        }

        try:
            await sender.send(payload)
        except Exception as exc:
            logger.warning("Webhook delivery error: %s", exc)

    async def _budget_pre_check(
        self,
        spec: WorkflowSpec,
        run_id: str,
        node_id: str,
        node_max: float,
    ) -> str | None:
        """Check node budget before a retry attempt.

        Returns an error message if the retry should be skipped, None otherwise.
        """
        all_costs = await self.execution_store.list_costs(run_id)
        node_cost = sum(r.cost for r in all_costs if r.task_id == node_id)
        remaining = node_max - node_cost

        if remaining > 0:
            return None

        policy = get_effective_policy(spec)
        if policy == "stop":
            msg = (
                f"Node '{node_id}': budget exhausted "
                f"(${node_cost:.2f}/${node_max:.2f}), skipping retry"
            )
            logger.warning(msg)
            click.echo(f"\u26a0 {msg}", err=True)
            return msg

        # warn — interactive prompt
        proceed = click.confirm(
            f"\u26a0 Node '{node_id}' retry will likely exceed budget "
            f"(${remaining:.2f} remaining of ${node_max:.2f}). "
            f"Continue?",
            default=False,
        )
        if not proceed:
            return f"Node '{node_id}': retry cancelled by user (budget)"
        return None

    async def _budget_post_check(
        self,
        spec: WorkflowSpec,
        run_id: str,
        node_id: str,
        node_max: float,
    ) -> bool:
        """Check node budget after execution. Returns True if budget exceeded with stop policy."""
        all_costs = await self.execution_store.list_costs(run_id)
        node_cost = sum(r.cost for r in all_costs if r.task_id == node_id)

        if node_cost <= node_max:
            return False

        policy = get_effective_policy(spec)
        if policy == "stop":
            msg = (
                f"Node '{node_id}': exceeded budget "
                f"${node_cost:.2f} / ${node_max:.2f}"
            )
            logger.warning(msg)
            click.echo(f"\u26a0 {msg}", err=True)
            return True

        # warn policy — keep result
        msg = (
            f"Node '{node_id}': exceeded budget "
            f"${node_cost:.2f} / ${node_max:.2f} "
            f"(policy: warn, keeping result)"
        )
        logger.warning(msg)
        click.echo(f"\u26a0 {msg}", err=True)
        return False

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
        node_artifacts_history: dict[str, list[list[Artifact]]] | None = None,
    ) -> None:
        if node_artifacts_history is None:
            node_artifacts_history = {}
        node_spec = spec.nodes[node_id]
        retry_policy = node_spec.retry_policy or (
            spec.defaults.retry_policy if spec.defaults else None
        )
        node_max = get_node_max_cost(node_spec, spec, accumulated_cost)

        task, max_retries = self._build_task_node(
            spec, run_id, node_id, node_spec, retry_policy, node_max,
        )

        input_artifacts = collect_input_artifacts(
            dag, node_id, node_artifacts,
            self._pending_feedback.pop(node_id, []),
        )

        start_ms = now_ms()
        await self._emit_event({
            "type": "node:started",
            "run_id": run_id,
            "node_id": node_id,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        succeeded, error_msg, output_artifacts = await self._retry_loop(
            spec, run_id, node_id, task, input_artifacts, trace_id,
            node_max, max_retries, retry_policy, node_artifacts,
        )

        if succeeded:
            scheduler.mark_completed(node_id)
            status = task.status.__class__("completed")
            # Evaluate back-edge after successful completion
            await evaluate_back_edge(
                spec, scheduler, dag, node_id,
                node_artifacts, node_artifacts_history,
                self._pending_feedback,
            )
        else:
            scheduler.mark_failed(node_id)
            status = task.status.__class__("failed")

        latency = now_ms() - start_ms
        await self._emit_event({
            "type": f"node:{'completed' if succeeded else 'failed'}",
            "run_id": run_id,
            "node_id": node_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "latency_ms": latency,
            **({"error": error_msg} if error_msg else {}),
        })

        latency_ms = now_ms() - start_ms
        await record_execution(
            self.execution_store,
            run_id=run_id,
            node_id=node_id,
            agent_id=node_spec.agent,
            status=status,
            input_artifacts=input_artifacts,
            output_artifacts=output_artifacts,
            latency_ms=latency_ms,
            trace_id=trace_id,
            error=error_msg,
        )

    @staticmethod
    def _build_task_node(
        spec: WorkflowSpec,
        run_id: str,
        node_id: str,
        node_spec: NodeSpec,
        retry_policy,
        node_max: float | None,
    ) -> tuple[TaskNode, int]:
        """Build a TaskNode and determine max retries.

        Returns (task, max_retries).
        """
        has_node_budget = node_spec.budget is not None
        if has_node_budget:
            max_retries = retry_policy.max_retries if retry_policy else 1
            task_retry_policy = None  # orchestrator handles retry
        else:
            max_retries = 1  # single attempt, dispatcher handles retry
            task_retry_policy = retry_policy

        # Build config dict, injecting output_schema if present
        config = dict(node_spec.config)
        if node_spec.output_schema is not None:
            config["output_schema"] = node_spec.output_schema

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
            config=config,
        )
        return task, max_retries

    async def _execute_single_attempt(
        self,
        spec: WorkflowSpec,
        run_id: str,
        node_id: str,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        node_max: float | None,
        node_artifacts: dict[str, list[Artifact]],
    ) -> tuple[bool, str | None, list[Artifact]]:
        """Execute a single dispatch attempt with cost recording and artifact storage.

        Returns (succeeded, error_msg, output_artifacts).
        Raises on dispatch failure so the caller can handle retries.
        """
        result = await self.dispatcher.dispatch(
            task, input_artifacts, trace_id,
            stream=self._stream,
            stream_callback=self._stream_callback,
        )
        output_artifacts = result.artifacts

        if result.cost:
            if node_max is not None:
                result.cost.node_budget = node_max
            await self.execution_store.record_cost(result.cost)

        if node_max is not None and result.cost:
            if await self._budget_post_check(
                spec, run_id, node_id, node_max,
            ):
                error_msg = (
                    f"Node '{node_id}': exceeded budget "
                    f"(stop policy)"
                )
                return False, error_msg, []

        for art in output_artifacts:
            await self.artifact_store.store(art)
        node_artifacts[node_id] = output_artifacts
        return True, None, output_artifacts

    async def _retry_loop(
        self,
        spec: WorkflowSpec,
        run_id: str,
        node_id: str,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        node_max: float | None,
        max_retries: int,
        retry_policy,
        node_artifacts: dict[str, list[Artifact]],
    ) -> tuple[bool, str | None, list[Artifact]]:
        """Execute dispatch with retries and budget checks.

        Returns (succeeded, error_msg, output_artifacts).
        """
        error_msg: str | None = None
        output_artifacts: list[Artifact] = []

        for attempt in range(1, max_retries + 1):
            if attempt > 1 and node_max is not None:
                pre_check_err = await self._budget_pre_check(
                    spec, run_id, node_id, node_max,
                )
                if pre_check_err:
                    return False, pre_check_err, output_artifacts

            try:
                return await self._execute_single_attempt(
                    spec, run_id, node_id, task, input_artifacts,
                    trace_id, node_max, node_artifacts,
                )
            except Exception as exc:
                error_msg = str(exc)
                if attempt < max_retries:
                    backoff = (
                        retry_policy.backoff if retry_policy else "exponential"
                    )
                    delay = _backoff_delay(attempt, backoff)
                    await asyncio.sleep(delay)

        return False, error_msg, output_artifacts
