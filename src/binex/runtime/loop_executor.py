"""Loop executor — iterative execution of loop container nodes."""

from __future__ import annotations

import asyncio
import json
import logging
import operator as op
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact, Lineage
from binex.models.workflow import LoopExitCondition, WorkflowSpec
from binex.runtime._node_executor import now_ms, record_execution
from binex.runtime.budget import get_node_max_cost
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore

logger = logging.getLogger(__name__)


class MaxIterationsExceededError(Exception):
    """Raised when loop max_iterations is reached without exit condition being met."""


# Keep backward-compatible alias
MaxIterationsExceeded = MaxIterationsExceededError


class LoopTimeoutExceededError(Exception):
    """Raised when loop timeout_minutes is exceeded."""


# Keep backward-compatible alias
LoopTimeoutExceeded = LoopTimeoutExceededError


_OPERATOR_MAP = {
    ">=": op.ge,
    "<=": op.le,
    ">": op.gt,
    "<": op.lt,
    "==": op.eq,
    "!=": op.ne,
}


def evaluate_jsonpath(data: Any, path: str) -> Any:
    """Evaluate a simple JSONPath expression ($.field.subfield) against data.

    Supports only dot notation: $.field, $.field.nested, etc.
    """
    if not path.startswith("$."):
        raise ValueError(f"JSONPath must start with '$.' , got {path!r}")

    parts = path[2:].split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                raise KeyError(f"JSONPath '{path}': key '{part}' not found in {current!r}")
            current = current[part]
        else:
            raise TypeError(
                f"JSONPath '{path}': cannot access '{part}' on {type(current).__name__}"
            )
    return current


def check_exit_condition(exit_cond: LoopExitCondition, data: Any) -> bool:
    """Check if the exit condition is met against the given data."""
    try:
        actual = evaluate_jsonpath(data, exit_cond.field)
    except (KeyError, TypeError):
        return False

    comparator = _OPERATOR_MAP.get(exit_cond.operator)
    if comparator is None:
        return False

    try:
        # Coerce types for comparison (bool ⊂ int in Python, so exclude it)
        if (
            isinstance(exit_cond.value, (int, float))
            and not isinstance(exit_cond.value, bool)
            and isinstance(actual, str)
        ):
            actual = float(actual)
        elif isinstance(exit_cond.value, str) and isinstance(actual, (int, float)):
            actual = str(actual)
        return comparator(actual, exit_cond.value)
    except (ValueError, TypeError):
        return False


def _parse_artifact_content(artifact: Artifact) -> Any:
    """Try to parse artifact content as JSON, fallback to raw string."""
    try:
        return json.loads(artifact.content)
    except (json.JSONDecodeError, TypeError):
        return artifact.content


class LoopExecutor:
    """Executes a loop container node iteratively."""

    # Minimum interval between loop:iteration SSE events (milliseconds).
    # Prevents flooding the SSE channel when loops run 100+ iterations.
    LOOP_EVENT_THROTTLE_MS: int = 500

    def __init__(
        self,
        artifact_store: ArtifactStore,
        execution_store: ExecutionStore,
        dispatcher: Any,  # Dispatcher
        *,
        stream: bool = False,
        stream_callback: Callable[[str], None] | None = None,
        event_callback: Callable[[dict], Any] | None = None,
        loop_event_throttle_ms: int | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.execution_store = execution_store
        self.dispatcher = dispatcher
        self._stream = stream
        self._stream_callback = stream_callback
        self._event_callback = event_callback
        self._loop_event_throttle_ms = (
            loop_event_throttle_ms
            if loop_event_throttle_ms is not None
            else self.LOOP_EVENT_THROTTLE_MS
        )

    async def _emit_event(self, event: dict) -> None:
        if self._event_callback is not None:
            result = self._event_callback(event)
            if asyncio.iscoroutine(result):
                await result

    async def _emit_loop_iteration_throttled(
        self,
        event: dict,
        last_emit_time: float,
        *,
        force: bool = False,
    ) -> float:
        """Emit loop:iteration event with time-based throttling.

        Returns the updated last_emit_time (monotonic seconds).
        If the event is throttled (not emitted), returns the original time unchanged.
        """
        now = time.monotonic()
        elapsed_ms = (now - last_emit_time) * 1000
        if force or elapsed_ms >= self._loop_event_throttle_ms:
            await self._emit_event(event)
            return now
        return last_emit_time

    async def execute_loop(
        self,
        spec: WorkflowSpec,
        dag: DAG,
        run_id: str,
        trace_id: str,
        loop_node_id: str,
        input_artifacts: list[Artifact],
        accumulated_cost: float = 0.0,
    ) -> tuple[list[Artifact], str | None]:
        """Execute a loop container node.

        Returns (output_artifacts, error_message).
        """
        node_spec = spec.nodes[loop_node_id]
        loop_spec = node_spec.loop
        assert loop_spec is not None

        sub_dag = dag.get_loop_subgraph(loop_node_id)
        contains = loop_spec.contains

        await self._emit_event({
            "type": "loop:started",
            "run_id": run_id,
            "node_id": loop_node_id,
            "max_iterations": loop_spec.max_iterations,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        start_time = time.monotonic()
        all_iteration_outputs: list[list[Artifact]] = []
        current_input = input_artifacts
        last_output: list[Artifact] = []
        last_iter_emit_time = 0.0  # force first iteration to emit

        for iteration in range(1, loop_spec.max_iterations + 1):
            is_last = iteration == loop_spec.max_iterations

            # Check timeout
            if loop_spec.timeout_minutes is not None:
                elapsed = time.monotonic() - start_time
                if elapsed > loop_spec.timeout_minutes * 60:
                    # Force-emit final iteration state before timeout event
                    await self._emit_loop_iteration_throttled(
                        {
                            "type": "loop:iteration",
                            "run_id": run_id,
                            "node_id": loop_node_id,
                            "iteration": iteration,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        last_iter_emit_time,
                        force=True,
                    )
                    await self._emit_event({
                        "type": "loop:timeout",
                        "run_id": run_id,
                        "node_id": loop_node_id,
                        "iteration": iteration,
                        "timestamp": datetime.now(UTC).isoformat(),
                    })
                    return [], (
                        f"Loop '{loop_node_id}': timeout after"
                        f" {loop_spec.timeout_minutes} minutes"
                    )

            last_iter_emit_time = await self._emit_loop_iteration_throttled(
                {
                    "type": "loop:iteration",
                    "run_id": run_id,
                    "node_id": loop_node_id,
                    "iteration": iteration,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                last_iter_emit_time,
                force=is_last,  # always emit last possible iteration
            )

            # Execute inner nodes
            inner_artifacts, error = await self._execute_inner_iteration(
                spec, sub_dag, run_id, trace_id,
                loop_node_id, contains, current_input,
                iteration, accumulated_cost,
            )

            if error:
                return [], error

            last_output = inner_artifacts
            all_iteration_outputs.append(inner_artifacts)

            # Use output of last iteration for exit check
            last_node_artifacts = inner_artifacts

            # Check exit condition
            exit_met = self._check_exit(loop_spec.exit, last_node_artifacts)
            if exit_met:
                # Force-emit final iteration state before completion
                await self._emit_loop_iteration_throttled(
                    {
                        "type": "loop:iteration",
                        "run_id": run_id,
                        "node_id": loop_node_id,
                        "iteration": iteration,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    last_iter_emit_time,
                    force=True,
                )
                await self._emit_event({
                    "type": "loop:completed",
                    "run_id": run_id,
                    "node_id": loop_node_id,
                    "iterations": iteration,
                    "timestamp": datetime.now(UTC).isoformat(),
                })
                if loop_spec.accumulate:
                    return self._build_accumulated_output(
                        run_id, loop_node_id, all_iteration_outputs,
                    ), None
                return last_output, None

            # Prepare input for next iteration
            if loop_spec.accumulate:
                current_input = self._build_accumulated_output(
                    run_id, loop_node_id, all_iteration_outputs,
                )
            else:
                current_input = last_output

        # Max iterations exceeded — final iteration already force-emitted (is_last=True)
        await self._emit_event({
            "type": "loop:max_iterations",
            "run_id": run_id,
            "node_id": loop_node_id,
            "iterations": loop_spec.max_iterations,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        return [], f"Loop '{loop_node_id}': max iterations ({loop_spec.max_iterations}) exceeded"

    async def _execute_inner_iteration(
        self,
        spec: WorkflowSpec,
        sub_dag: DAG,
        run_id: str,
        trace_id: str,
        loop_node_id: str,
        contains: list[str],
        input_artifacts: list[Artifact],
        iteration: int,
        accumulated_cost: float,
    ) -> tuple[list[Artifact], str | None]:
        """Execute one iteration of the loop's inner nodes.

        Returns (output_artifacts_of_last_node, error).
        """
        inner_scheduler = Scheduler(sub_dag)
        node_artifacts: dict[str, list[Artifact]] = {}

        # Entry nodes get input artifacts
        loop_spec = spec.nodes[loop_node_id].loop
        if loop_spec and loop_spec.entry_node:
            # Explicit entry_node — only it receives input
            node_artifacts[loop_spec.entry_node] = input_artifacts
        else:
            # Default: all nodes with no internal deps receive input
            entry_nodes = sub_dag.entry_nodes()
            for entry_id in entry_nodes:
                node_artifacts[entry_id] = input_artifacts

        while not inner_scheduler.is_complete() and not inner_scheduler.is_blocked():
            ready = inner_scheduler.ready_nodes()
            if not ready:
                await asyncio.sleep(0.01)
                continue

            tasks = []
            for node_id in ready:
                inner_scheduler.mark_running(node_id)
                tasks.append(
                    self._execute_inner_node(
                        spec, sub_dag, inner_scheduler, run_id, trace_id,
                        loop_node_id, node_id, node_artifacts,
                        iteration, accumulated_cost,
                    )
                )

            if tasks:
                await asyncio.gather(*tasks)

        # Determine output node
        if loop_spec and loop_spec.output_node:
            out_node = loop_spec.output_node
        else:
            topo = sub_dag.topological_order()
            out_node = topo[-1] if topo else contains[-1]

        # Check for failures
        if inner_scheduler._failed:
            # Hard fail if the designated output_node failed
            if out_node in inner_scheduler._failed:
                return [], (
                    f"Loop '{loop_node_id}' iteration {iteration}: "
                    f"output node '{out_node}' failed"
                )
            failed = ", ".join(sorted(inner_scheduler._failed))
            return [], f"Loop '{loop_node_id}' iteration {iteration}: nodes failed: {failed}"

        return node_artifacts.get(out_node, []), None

    async def _execute_inner_node(
        self,
        spec: WorkflowSpec,
        sub_dag: DAG,
        inner_scheduler: Scheduler,
        run_id: str,
        trace_id: str,
        loop_node_id: str,
        node_id: str,
        node_artifacts: dict[str, list[Artifact]],
        iteration: int,
        accumulated_cost: float,
    ) -> None:
        """Execute a single node within a loop iteration."""
        from binex.models.task import TaskNode
        node_spec = spec.nodes[node_id]
        node_max = get_node_max_cost(node_spec, spec, accumulated_cost)
        retry_policy = node_spec.retry_policy or (
            spec.defaults.retry_policy if spec.defaults else None
        )

        config = dict(node_spec.config)
        if node_spec.output_schema is not None:
            config["output_schema"] = node_spec.output_schema

        task = TaskNode(
            id=f"{run_id}_{loop_node_id}_{node_id}_iter{iteration}",
            run_id=run_id,
            node_id=node_id,
            agent=node_spec.agent,
            system_prompt=node_spec.system_prompt,
            tools=node_spec.tools,
            inputs=node_spec.inputs,
            retry_policy=retry_policy,
            deadline_ms=node_spec.deadline_ms or (
                spec.defaults.deadline_ms if spec.defaults else None
            ),
            config=config,
        )

        # Collect inputs from internal dependencies
        inputs: list[Artifact] = []
        for dep_id in sub_dag.dependencies(node_id):
            inputs.extend(node_artifacts.get(dep_id, []))
        # Entry nodes: use loop input (already in node_artifacts)
        if not sub_dag.dependencies(node_id) and node_id in node_artifacts:
            inputs = node_artifacts[node_id]

        start_ms = now_ms()
        await self._emit_event({
            "type": "node:started",
            "run_id": run_id,
            "node_id": f"{loop_node_id}.{node_id}",
            "iteration": iteration,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        try:
            result = await self.dispatcher.dispatch(
                task, inputs, trace_id,
                stream=self._stream,
                stream_callback=self._stream_callback,
            )
            output_artifacts = result.artifacts

            if result.cost:
                if node_max is not None:
                    result.cost.node_budget = node_max
                await self.execution_store.record_cost(result.cost)

            for art in output_artifacts:
                await self.artifact_store.store(art)
            node_artifacts[node_id] = output_artifacts

            inner_scheduler.mark_completed(node_id)
            status_val = "completed"
            error_msg = None
        except Exception as exc:
            inner_scheduler.mark_failed(node_id)
            output_artifacts = []
            status_val = "failed"
            error_msg = str(exc)

        latency_ms = now_ms() - start_ms

        from binex.models.task import TaskStatus
        await record_execution(
            self.execution_store,
            run_id=run_id,
            node_id=f"{loop_node_id}.{node_id}",
            agent_id=node_spec.agent,
            status=TaskStatus(status_val),
            input_artifacts=inputs,
            output_artifacts=output_artifacts,
            latency_ms=latency_ms,
            trace_id=trace_id,
            error=error_msg,
            iteration_number=iteration,
        )

        await self._emit_event({
            "type": f"node:{'completed' if status_val == 'completed' else 'failed'}",
            "run_id": run_id,
            "node_id": f"{loop_node_id}.{node_id}",
            "iteration": iteration,
            "timestamp": datetime.now(UTC).isoformat(),
            "latency_ms": latency_ms,
            **({"error": error_msg} if error_msg else {}),
        })

    def _check_exit(
        self,
        exit_cond: LoopExitCondition,
        artifacts: list[Artifact],
    ) -> bool:
        """Check exit condition against the last output artifacts."""
        for artifact in reversed(artifacts):
            data = _parse_artifact_content(artifact)
            if check_exit_condition(exit_cond, data):
                return True
        return False

    @staticmethod
    def _build_accumulated_output(
        run_id: str,
        loop_node_id: str,
        all_outputs: list[list[Artifact]],
    ) -> list[Artifact]:
        """Build accumulated output artifact containing all iteration results."""
        iterations_data = []
        for i, outputs in enumerate(all_outputs, 1):
            for art in outputs:
                iterations_data.append({
                    "iteration": i,
                    "artifact_id": art.id,
                    "type": art.type,
                    "content": art.content,
                })

        accumulated = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            type="loop_accumulated",
            content=json.dumps({"iterations": iterations_data}),
            lineage=Lineage(produced_by=loop_node_id),
        )
        return [accumulated]
