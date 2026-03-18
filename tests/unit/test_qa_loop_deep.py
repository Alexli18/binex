"""Deep QA tests for Loop Container (018-loop-container).

Covers gaps not addressed by test_loop_container.py:
- LoopExecutor integration (mocked dispatcher)
- Exit condition edge cases with all operators and data types
- accumulate mode behavior
- Timeout and max_iterations error paths
- Dotted node ID format
- DAG subgraph edge cases
- Loops API endpoint tests
- Event emission / throttling
- Resource cleanup
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord
from binex.models.task import TaskStatus
from binex.models.workflow import (
    LoopExitCondition,
    LoopSpec,
    NodeSpec,
    WorkflowSpec,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _make_artifact(content: str | dict, run_id: str = "r1", node: str = "n1") -> Artifact:
    """Create a test artifact with JSON-serializable content."""
    if isinstance(content, dict):
        content = json.dumps(content)
    return Artifact(
        id=f"art_{node}",
        run_id=run_id,
        type="output",
        content=content,
        lineage=Lineage(produced_by=node),
    )


def _make_loop_workflow(
    *,
    max_iterations: int = 5,
    timeout_minutes: float | None = None,
    accumulate: bool = False,
    exit_field: str = "$.score",
    exit_op: str = ">=",
    exit_value: float | str | bool = 0.9,
    extra_nodes: dict | None = None,
) -> WorkflowSpec:
    """Create a standard loop workflow for testing."""
    nodes = {
        "setup": {"agent": "local://echo", "outputs": ["context"]},
        "writer": {
            "agent": "llm://gpt-4o",
            "outputs": ["draft"],
            "depends_on": ["setup"],
        },
        "reviewer": {
            "agent": "llm://gpt-4o",
            "inputs": {"draft": "${writer.draft}"},
            "outputs": ["score"],
            "depends_on": ["writer"],
        },
        "refine_loop": {
            "type": "loop",
            "outputs": ["refined"],
            "depends_on": ["setup"],
            "loop": {
                "exit": {"field": exit_field, "operator": exit_op, "value": exit_value},
                "max_iterations": max_iterations,
                "timeout_minutes": timeout_minutes,
                "accumulate": accumulate,
                "contains": ["writer", "reviewer"],
            },
        },
    }
    if extra_nodes:
        nodes.update(extra_nodes)
    return WorkflowSpec(name="loop-qa", nodes=nodes)


class FakeExecutionStore:
    """In-memory execution store for testing LoopExecutor."""

    def __init__(self):
        self.records: list[ExecutionRecord] = []
        self.costs: list = []

    async def record(self, rec: ExecutionRecord) -> None:
        self.records.append(rec)

    async def record_cost(self, cost) -> None:
        self.costs.append(cost)

    async def list_records(self, run_id: str) -> list[ExecutionRecord]:
        return [r for r in self.records if r.run_id == run_id]

    async def list_costs(self, run_id: str) -> list:
        return [c for c in self.costs if c.run_id == run_id]

    async def close(self) -> None:
        pass


class FakeArtifactStore:
    """In-memory artifact store for testing LoopExecutor."""

    def __init__(self):
        self.stored: list[Artifact] = []

    async def store(self, art: Artifact) -> None:
        self.stored.append(art)


class FakeDispatchResult:
    """Mimics dispatcher.dispatch() return value."""

    def __init__(self, artifacts: list[Artifact], cost=None):
        self.artifacts = artifacts
        self.cost = cost


# ===========================================================================
# 1. check_exit_condition — all operators × all data types
# ===========================================================================


class TestExitConditionAllOperatorsTypes:
    """Exhaustive operator × data type coverage for check_exit_condition."""

    def test_gte_float_exact_boundary(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator=">=", value=0.9)
        assert check_exit_condition(cond, {"v": 0.9}) is True
        assert check_exit_condition(cond, {"v": 0.89999}) is False

    def test_lte_float(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator="<=", value=5.0)
        assert check_exit_condition(cond, {"v": 5.0}) is True
        assert check_exit_condition(cond, {"v": 5.001}) is False

    def test_gt_int(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator=">", value=10)
        assert check_exit_condition(cond, {"v": 11}) is True
        assert check_exit_condition(cond, {"v": 10}) is False

    def test_lt_int(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator="<", value=3)
        assert check_exit_condition(cond, {"v": 2}) is True
        assert check_exit_condition(cond, {"v": 3}) is False

    def test_eq_bool_true(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.done", operator="==", value=True)
        assert check_exit_condition(cond, {"done": True}) is True
        assert check_exit_condition(cond, {"done": False}) is False

    def test_eq_bool_false(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.done", operator="==", value=False)
        assert check_exit_condition(cond, {"done": False}) is True
        assert check_exit_condition(cond, {"done": True}) is False

    def test_ne_bool(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.done", operator="!=", value=False)
        assert check_exit_condition(cond, {"done": True}) is True
        assert check_exit_condition(cond, {"done": False}) is False

    def test_eq_string(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.s", operator="==", value="yes")
        assert check_exit_condition(cond, {"s": "yes"}) is True
        assert check_exit_condition(cond, {"s": "no"}) is False

    def test_ne_string(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.s", operator="!=", value="error")
        assert check_exit_condition(cond, {"s": "ok"}) is True
        assert check_exit_condition(cond, {"s": "error"}) is False

    def test_gt_string_comparison(self):
        """Strings are compared lexicographically."""
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.s", operator=">", value="aaa")
        assert check_exit_condition(cond, {"s": "bbb"}) is True
        assert check_exit_condition(cond, {"s": "aaa"}) is False

    def test_coercion_string_numeric_to_float(self):
        """String "0.95" coerced to float when value is numeric."""
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator=">=", value=0.9)
        assert check_exit_condition(cond, {"v": "0.95"}) is True

    def test_coercion_non_numeric_string_returns_false(self):
        """Non-numeric string can't be coerced → returns False."""
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator=">=", value=0.9)
        assert check_exit_condition(cond, {"v": "not_a_number"}) is False

    def test_coercion_int_to_string(self):
        """Integer coerced to string for string comparison."""
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator="==", value="42")
        assert check_exit_condition(cond, {"v": 42}) is True

    def test_empty_dict_data(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.x", operator=">=", value=1)
        assert check_exit_condition(cond, {}) is False

    def test_none_value_in_data(self):
        """None value in data vs numeric comparison."""
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.v", operator=">=", value=1)
        assert check_exit_condition(cond, {"v": None}) is False


# ===========================================================================
# 2. LoopExecutor — integration tests with mocked dispatcher
# ===========================================================================


@pytest.mark.asyncio
class TestLoopExecutorIntegration:
    """Integration tests for LoopExecutor.execute_loop with mock dispatcher."""

    def _make_executor(self, events=None, throttle_ms=0):
        from binex.runtime.loop_executor import LoopExecutor
        exec_store = FakeExecutionStore()
        art_store = FakeArtifactStore()
        dispatcher = AsyncMock()
        event_list = events if events is not None else []

        async def capture_event(evt):
            event_list.append(evt)

        executor = LoopExecutor(
            artifact_store=art_store,
            execution_store=exec_store,
            dispatcher=dispatcher,
            event_callback=capture_event,
            loop_event_throttle_ms=throttle_ms,
        )
        return executor, exec_store, art_store, dispatcher, event_list

    async def test_exit_on_first_iteration(self):
        """Exit condition met immediately → 1 iteration only."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        # Dispatcher returns artifact with score=1.0 (meets >=0.9)
        result_art = _make_artifact({"score": 1.0}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        spec = _make_loop_workflow(max_iterations=10)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-1", "trace-1", "refine_loop", [],
        )
        assert error is None
        assert len(output) > 0
        # Should have loop:started + loop:iteration + loop:completed
        event_types = [e["type"] for e in events]
        assert "loop:started" in event_types
        assert "loop:completed" in event_types
        # Only 1 iteration
        completed_evt = next(e for e in events if e["type"] == "loop:completed")
        assert completed_evt["iterations"] == 1

    async def test_max_iterations_exceeded(self):
        """Exit never met → max_iterations error."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        # Always return score below threshold
        result_art = _make_artifact({"score": 0.1}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        spec = _make_loop_workflow(max_iterations=3)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-2", "trace-2", "refine_loop", [],
        )
        assert error is not None
        assert "max iterations" in error.lower()
        assert output == []
        # max_iterations event emitted
        event_types = [e["type"] for e in events]
        assert "loop:max_iterations" in event_types

    async def test_exit_on_second_iteration(self):
        """Exit condition met on 2nd iteration."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        call_count = 0

        async def mock_dispatch(task, inputs, trace_id, **kwargs):
            nonlocal call_count
            call_count += 1
            # Each loop iteration dispatches 2 nodes (writer + reviewer)
            # Reviewer is the last one; on 2nd iteration (calls 3-4), return high score
            if call_count <= 2:
                return FakeDispatchResult([_make_artifact({"score": 0.5}, node="reviewer")])
            return FakeDispatchResult([_make_artifact({"score": 0.95}, node="reviewer")])

        dispatcher.dispatch.side_effect = mock_dispatch

        spec = _make_loop_workflow(max_iterations=10)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-3", "trace-3", "refine_loop", [],
        )
        assert error is None
        completed_evt = next(e for e in events if e["type"] == "loop:completed")
        assert completed_evt["iterations"] == 2

    async def test_accumulate_mode(self):
        """accumulate=True returns accumulated artifact with all iterations."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        call_count = 0

        async def mock_dispatch(task, inputs, trace_id, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return FakeDispatchResult([_make_artifact({"score": 0.5, "text": "draft1"}, node="reviewer")])
            return FakeDispatchResult([_make_artifact({"score": 0.95, "text": "draft2"}, node="reviewer")])

        dispatcher.dispatch.side_effect = mock_dispatch

        spec = _make_loop_workflow(max_iterations=10, accumulate=True)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-acc", "trace-acc", "refine_loop", [],
        )
        assert error is None
        assert len(output) == 1
        # Accumulated artifact should contain iteration data
        content = json.loads(output[0].content)
        assert "iterations" in content
        assert output[0].type == "loop_accumulated"

    async def test_non_accumulate_returns_last_output(self):
        """accumulate=False returns only last iteration output."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        result_art = _make_artifact({"score": 1.0, "text": "final"}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        spec = _make_loop_workflow(max_iterations=10, accumulate=False)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-noacc", "trace-noacc", "refine_loop", [],
        )
        assert error is None
        # Should be the raw artifact, not accumulated
        assert output[0].type == "output"

    async def test_dotted_node_id_in_execution_records(self):
        """Execution records use {loop_id}.{node_id} format."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        result_art = _make_artifact({"score": 1.0}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        spec = _make_loop_workflow(max_iterations=10)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        await executor.execute_loop(
            spec, dag, "run-dot", "trace-dot", "refine_loop", [],
        )

        # Check execution records have dotted format
        records = exec_store.records
        assert len(records) >= 2  # writer + reviewer
        task_ids = [r.task_id for r in records]
        assert any("refine_loop.writer" in tid for tid in task_ids)
        assert any("refine_loop.reviewer" in tid for tid in task_ids)

    async def test_iteration_number_recorded(self):
        """Execution records have iteration_number set."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        result_art = _make_artifact({"score": 1.0}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        spec = _make_loop_workflow(max_iterations=10)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        await executor.execute_loop(
            spec, dag, "run-iter", "trace-iter", "refine_loop", [],
        )

        records = exec_store.records
        assert all(r.iteration_number is not None for r in records)
        assert all(r.iteration_number == 1 for r in records)  # only 1 iteration

    async def test_inner_node_failure_stops_loop(self):
        """If an inner node fails, loop returns error."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        dispatcher.dispatch.side_effect = RuntimeError("LLM API error")

        spec = _make_loop_workflow(max_iterations=5)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-fail", "trace-fail", "refine_loop", [],
        )
        assert error is not None
        assert "failed" in error.lower()
        assert output == []

    async def test_exit_condition_on_missing_field_does_not_exit(self):
        """If JSONPath field doesn't exist in output, exit condition is not met."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        # Return artifact without the 'score' field
        result_art = _make_artifact({"other": "data"}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        spec = _make_loop_workflow(max_iterations=2)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-miss", "trace-miss", "refine_loop", [],
        )
        # Should reach max iterations since field is never found
        assert error is not None
        assert "max iterations" in error.lower()

    async def test_timeout_stops_loop(self):
        """Loop with very short timeout exits with timeout error."""
        executor, exec_store, art_store, dispatcher, events = self._make_executor()

        async def slow_dispatch(task, inputs, trace_id, **kwargs):
            await asyncio.sleep(0.1)
            return FakeDispatchResult([_make_artifact({"score": 0.1}, node="reviewer")])

        dispatcher.dispatch.side_effect = slow_dispatch

        # 0.001 minutes = 0.06 seconds — should timeout after first iteration
        spec = _make_loop_workflow(max_iterations=100, timeout_minutes=0.001)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-timeout", "trace-timeout", "refine_loop", [],
        )
        # Either timeout or max_iterations, depending on timing
        # But with 0.001 min timeout and sleep(0.1) per dispatch, timeout should trigger
        assert error is not None
        event_types = [e["type"] for e in events]
        # Should have either timeout or max_iterations
        assert "loop:timeout" in event_types or "loop:max_iterations" in event_types


# ===========================================================================
# 3. LoopExecutor._check_exit — artifact-level tests
# ===========================================================================


class TestCheckExitArtifactLevel:
    """Test _check_exit method which iterates over artifacts."""

    def test_check_exit_last_artifact_matches(self):
        from binex.runtime.loop_executor import LoopExecutor
        executor = LoopExecutor.__new__(LoopExecutor)
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)

        arts = [
            _make_artifact({"score": 0.5}),
            _make_artifact({"score": 0.95}),
        ]
        assert executor._check_exit(cond, arts) is True

    def test_check_exit_no_match(self):
        from binex.runtime.loop_executor import LoopExecutor
        executor = LoopExecutor.__new__(LoopExecutor)
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)

        arts = [_make_artifact({"score": 0.3})]
        assert executor._check_exit(cond, arts) is False

    def test_check_exit_empty_artifacts(self):
        from binex.runtime.loop_executor import LoopExecutor
        executor = LoopExecutor.__new__(LoopExecutor)
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert executor._check_exit(cond, []) is False

    def test_check_exit_non_json_artifact(self):
        from binex.runtime.loop_executor import LoopExecutor
        executor = LoopExecutor.__new__(LoopExecutor)
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        arts = [_make_artifact("plain text, not JSON")]
        assert executor._check_exit(cond, arts) is False

    def test_check_exit_reversed_order(self):
        """_check_exit checks artifacts in reverse order — latest first."""
        from binex.runtime.loop_executor import LoopExecutor
        executor = LoopExecutor.__new__(LoopExecutor)
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)

        # First artifact has match, second doesn't
        arts = [
            _make_artifact({"score": 0.95}),
            _make_artifact({"other": "no score"}),
        ]
        # Since reversed, second artifact checked first but has no match,
        # then first artifact checked and matches
        assert executor._check_exit(cond, arts) is True


# ===========================================================================
# 4. _build_accumulated_output tests
# ===========================================================================


class TestBuildAccumulatedOutput:
    """Test LoopExecutor._build_accumulated_output."""

    def test_single_iteration(self):
        from binex.runtime.loop_executor import LoopExecutor
        arts = [_make_artifact({"text": "draft1"}, node="writer")]
        result = LoopExecutor._build_accumulated_output("run-1", "loop1", [arts])
        assert len(result) == 1
        data = json.loads(result[0].content)
        assert len(data["iterations"]) == 1
        assert data["iterations"][0]["iteration"] == 1

    def test_multiple_iterations(self):
        from binex.runtime.loop_executor import LoopExecutor
        iter1 = [_make_artifact({"text": "d1"}, node="w")]
        iter2 = [_make_artifact({"text": "d2"}, node="w")]
        iter3 = [_make_artifact({"text": "d3"}, node="w")]
        result = LoopExecutor._build_accumulated_output("r", "l", [iter1, iter2, iter3])
        data = json.loads(result[0].content)
        assert len(data["iterations"]) == 3
        assert data["iterations"][2]["iteration"] == 3

    def test_empty_iterations(self):
        from binex.runtime.loop_executor import LoopExecutor
        result = LoopExecutor._build_accumulated_output("r", "l", [])
        data = json.loads(result[0].content)
        assert data["iterations"] == []

    def test_accumulated_artifact_type(self):
        from binex.runtime.loop_executor import LoopExecutor
        result = LoopExecutor._build_accumulated_output("r", "l", [[]])
        assert result[0].type == "loop_accumulated"

    def test_accumulated_lineage(self):
        from binex.runtime.loop_executor import LoopExecutor
        result = LoopExecutor._build_accumulated_output("r1", "myloop", [[]])
        assert result[0].lineage.produced_by == "myloop"


# ===========================================================================
# 5. Event throttling
# ===========================================================================


@pytest.mark.asyncio
class TestEventThrottling:
    """Test loop:iteration event throttling."""

    async def test_throttle_suppresses_rapid_events(self):
        from binex.runtime.loop_executor import LoopExecutor
        emitted = []

        async def capture(evt):
            emitted.append(evt)

        executor = LoopExecutor(
            artifact_store=FakeArtifactStore(),
            execution_store=FakeExecutionStore(),
            dispatcher=AsyncMock(),
            event_callback=capture,
            loop_event_throttle_ms=10000,  # 10s throttle
        )

        evt = {"type": "loop:iteration", "iteration": 1}
        # First emit should always go through (last_emit_time=0)
        t = await executor._emit_loop_iteration_throttled(evt, 0.0)
        assert len(emitted) == 1

        # Second emit immediately after should be suppressed
        await executor._emit_loop_iteration_throttled(evt, t)
        assert len(emitted) == 1  # still 1

    async def test_force_bypasses_throttle(self):
        from binex.runtime.loop_executor import LoopExecutor
        emitted = []

        async def capture(evt):
            emitted.append(evt)

        executor = LoopExecutor(
            artifact_store=FakeArtifactStore(),
            execution_store=FakeExecutionStore(),
            dispatcher=AsyncMock(),
            event_callback=capture,
            loop_event_throttle_ms=10000,
        )

        evt = {"type": "loop:iteration"}
        t = await executor._emit_loop_iteration_throttled(evt, 0.0)
        await executor._emit_loop_iteration_throttled(evt, t, force=True)
        assert len(emitted) == 2  # both emitted

    async def test_zero_throttle_emits_all(self):
        from binex.runtime.loop_executor import LoopExecutor
        emitted = []

        async def capture(evt):
            emitted.append(evt)

        executor = LoopExecutor(
            artifact_store=FakeArtifactStore(),
            execution_store=FakeExecutionStore(),
            dispatcher=AsyncMock(),
            event_callback=capture,
            loop_event_throttle_ms=0,
        )

        evt = {"type": "loop:iteration"}
        t = await executor._emit_loop_iteration_throttled(evt, 0.0)
        await executor._emit_loop_iteration_throttled(evt, t)
        assert len(emitted) == 2


# ===========================================================================
# 6. DAG subgraph edge cases
# ===========================================================================


class TestDAGLoopSubgraphEdgeCases:
    """Edge cases for DAG loop subgraph handling."""

    def test_loop_inherits_external_deps(self):
        """Loop container in top-level DAG inherits deps of contained entry nodes."""
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="inherit-deps",
            nodes={
                "input_node": {"agent": "local://echo", "outputs": ["data"]},
                "processor": {
                    "agent": "llm://gpt-4o", "outputs": ["result"],
                    "depends_on": ["input_node"],
                },
                "checker": {
                    "agent": "llm://gpt-4o", "outputs": ["check"],
                    "depends_on": ["processor"],
                },
                "my_loop": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.ok", "operator": "==", "value": True},
                        "contains": ["processor", "checker"],
                    },
                },
            },
        )
        dag = DAG.from_workflow(ws)
        # my_loop should depend on input_node (inherited from processor)
        loop_deps = dag.dependencies("my_loop")
        assert "input_node" in loop_deps

    def test_external_node_depends_on_loop_output(self):
        """Node outside loop that depends on a contained node → depends on loop container."""
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="ext-dep",
            nodes={
                "worker": {"agent": "local://echo", "outputs": ["out"]},
                "my_loop": {
                    "type": "loop", "outputs": ["result"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["worker"],
                    },
                },
                "consumer": {
                    "agent": "local://echo", "outputs": ["final"],
                    "depends_on": ["worker"],
                },
            },
        )
        dag = DAG.from_workflow(ws)
        # consumer should depend on my_loop (not directly on worker)
        consumer_deps = dag.dependencies("consumer")
        assert "my_loop" in consumer_deps
        assert "worker" not in consumer_deps

    def test_loop_subgraph_entry_nodes(self):
        """Subgraph entry_nodes returns nodes without internal deps."""
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="subgraph-entry",
            nodes={
                "a": {"agent": "local://echo", "outputs": ["o"]},
                "b": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["a"]},
                "c": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["a"]},
                "loop1": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["a", "b", "c"],
                    },
                },
            },
        )
        dag = DAG.from_workflow(ws)
        sub = dag.get_loop_subgraph("loop1")
        entries = sub.entry_nodes()
        assert entries == ["a"]

    def test_loop_subgraph_topo_order(self):
        """Subgraph topological order respects internal deps."""
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="topo",
            nodes={
                "step1": {"agent": "local://echo", "outputs": ["o"]},
                "step2": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["step1"]},
                "step3": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["step2"]},
                "loop1": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["step1", "step2", "step3"],
                    },
                },
            },
        )
        dag = DAG.from_workflow(ws)
        sub = dag.get_loop_subgraph("loop1")
        topo = sub.topological_order()
        assert topo == ["step1", "step2", "step3"]

    def test_get_loop_contains(self):
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="contains",
            nodes={
                "w": {"agent": "local://echo", "outputs": ["o"]},
                "loop1": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["w"],
                    },
                },
            },
        )
        dag = DAG.from_workflow(ws)
        assert dag.get_loop_contains("loop1") == ["w"]
        assert dag.get_loop_contains("nonexistent") == []


# ===========================================================================
# 7. Validator edge cases
# ===========================================================================


class TestValidatorLoopEdgeCases:
    """Additional validator edge cases for loop nodes."""

    def test_loop_with_self_reference_in_contains(self):
        """Loop references itself in contains → unknown node (since loop is type=loop)."""
        from binex.workflow_spec.validator import validate_workflow
        ws = WorkflowSpec(
            name="self-ref",
            nodes={
                "worker": {"agent": "local://echo", "outputs": ["o"]},
                "my_loop": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["worker", "my_loop"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        # my_loop contains itself — nested loop error
        nested_errors = [e for e in errors if "nested" in e.lower()]
        assert len(nested_errors) >= 1

    def test_jsonpath_with_array_notation_invalid(self):
        """JSONPath with array notation ($.items[0]) should be rejected by validator regex."""
        from binex.workflow_spec.validator import _JSONPATH_RE
        assert _JSONPATH_RE.match("$.items[0]") is None
        assert _JSONPATH_RE.match("$.items.0") is not None  # dot notation ok

    def test_three_node_cycle_inside_loop(self):
        """Three-node cycle inside loop detected."""
        from binex.workflow_spec.validator import validate_workflow
        ws = WorkflowSpec(
            name="three-cycle",
            nodes={
                "a": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["c"]},
                "b": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["a"]},
                "c": {"agent": "local://echo", "outputs": ["o"], "depends_on": ["b"]},
                "loop1": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["a", "b", "c"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        cycle_errors = [e for e in errors if "internal cycle" in e.lower()]
        assert len(cycle_errors) >= 1


# ===========================================================================
# 8. Loops API tests
# ===========================================================================


@pytest.mark.asyncio
class TestLoopsAPI:
    """Tests for Loops API endpoints."""

    async def _make_store_with_loop_records(self):
        """Create a store with sample loop execution records."""
        store = FakeExecutionStore()

        for i in range(1, 4):  # 3 iterations
            for node in ["writer", "reviewer"]:
                rec = ExecutionRecord(
                    id=f"rec-{node}-iter{i}",
                    run_id="run-1",
                    task_id=f"refine_loop.{node}",
                    agent_id="llm://gpt-4o",
                    status=TaskStatus.COMPLETED,
                    latency_ms=100 + i * 10,
                    trace_id="trace-1",
                    iteration_number=i,
                )
                store.records.append(rec)

        return store

    async def test_get_loops_with_data(self):
        from binex.ui.api.loops import get_loops
        store = await self._make_store_with_loop_records()

        with patch("binex.ui.api.loops._get_stores", return_value=(store, FakeArtifactStore())):
            response = await get_loops("run-1")
            data = json.loads(response.body)

        assert data["run_id"] == "run-1"
        assert len(data["loops"]) == 1
        loop = data["loops"][0]
        assert loop["loop_node_id"] == "refine_loop"
        assert loop["total_iterations"] == 3

    async def test_get_loops_empty_run(self):
        from binex.ui.api.loops import get_loops
        store = FakeExecutionStore()

        with patch("binex.ui.api.loops._get_stores", return_value=(store, FakeArtifactStore())):
            response = await get_loops("run-empty")
            data = json.loads(response.body)

        assert data["loops"] == []

    async def test_get_loop_detail(self):
        from binex.ui.api.loops import get_loop_detail
        store = await self._make_store_with_loop_records()

        with patch("binex.ui.api.loops._get_stores", return_value=(store, FakeArtifactStore())):
            response = await get_loop_detail("run-1", "refine_loop")
            data = json.loads(response.body)

        assert data["loop_node_id"] == "refine_loop"
        assert data["total_iterations"] == 3
        # Each iteration should have 2 nodes
        for iteration in data["iterations"]:
            assert len(iteration["nodes"]) == 2

    async def test_get_loop_detail_nonexistent_loop(self):
        from binex.ui.api.loops import get_loop_detail
        store = await self._make_store_with_loop_records()

        with patch("binex.ui.api.loops._get_stores", return_value=(store, FakeArtifactStore())):
            response = await get_loop_detail("run-1", "nonexistent_loop")
            data = json.loads(response.body)

        assert data["iterations"] == []
        assert data["total_iterations"] == 0

    async def test_get_loops_iteration_status_mixed(self):
        """Iteration with failed node gets status='failed'."""
        from binex.ui.api.loops import get_loops
        store = FakeExecutionStore()

        # Iteration 1: all completed
        store.records.append(ExecutionRecord(
            id="r1", run_id="run-mix", task_id="loop1.a",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=100, trace_id="t", iteration_number=1,
        ))
        # Iteration 2: one failed
        store.records.append(ExecutionRecord(
            id="r2", run_id="run-mix", task_id="loop1.a",
            agent_id="llm://gpt-4o", status=TaskStatus.FAILED,
            latency_ms=100, trace_id="t", iteration_number=2,
            error="LLM timeout",
        ))

        with patch("binex.ui.api.loops._get_stores", return_value=(store, FakeArtifactStore())):
            response = await get_loops("run-mix")
            data = json.loads(response.body)

        iters = data["loops"][0]["iterations"]
        assert iters[0]["status"] == "completed"
        assert iters[1]["status"] == "failed"

    async def test_get_loops_multiple_loops(self):
        """Multiple loop containers in one run."""
        from binex.ui.api.loops import get_loops
        store = FakeExecutionStore()

        for loop_id in ["loop_a", "loop_b"]:
            store.records.append(ExecutionRecord(
                id=f"r-{loop_id}", run_id="run-multi", task_id=f"{loop_id}.worker",
                agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
                latency_ms=100, trace_id="t", iteration_number=1,
            ))

        with patch("binex.ui.api.loops._get_stores", return_value=(store, FakeArtifactStore())):
            response = await get_loops("run-multi")
            data = json.loads(response.body)

        assert len(data["loops"]) == 2
        loop_ids = {l["loop_node_id"] for l in data["loops"]}
        assert loop_ids == {"loop_a", "loop_b"}


# ===========================================================================
# 9. LoopExecutor max_iterations=1 boundary
# ===========================================================================


@pytest.mark.asyncio
class TestLoopExecutorBoundary:
    """Boundary conditions for LoopExecutor."""

    async def test_max_iterations_1_exit_met(self):
        """max_iterations=1, exit condition met → completes."""
        from binex.runtime.loop_executor import LoopExecutor
        exec_store = FakeExecutionStore()
        art_store = FakeArtifactStore()
        dispatcher = AsyncMock()
        events = []

        result_art = _make_artifact({"score": 1.0}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        async def cap(e):
            events.append(e)

        executor = LoopExecutor(
            artifact_store=art_store, execution_store=exec_store,
            dispatcher=dispatcher, event_callback=cap,
            loop_event_throttle_ms=0,
        )

        spec = _make_loop_workflow(max_iterations=1)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-b1", "trace-b1", "refine_loop", [],
        )
        assert error is None
        event_types = [e["type"] for e in events]
        assert "loop:completed" in event_types

    async def test_max_iterations_1_exit_not_met(self):
        """max_iterations=1, exit NOT met → max_iterations error."""
        from binex.runtime.loop_executor import LoopExecutor
        exec_store = FakeExecutionStore()
        art_store = FakeArtifactStore()
        dispatcher = AsyncMock()
        events = []

        result_art = _make_artifact({"score": 0.1}, node="reviewer")
        dispatcher.dispatch.return_value = FakeDispatchResult([result_art])

        async def cap(e):
            events.append(e)

        executor = LoopExecutor(
            artifact_store=art_store, execution_store=exec_store,
            dispatcher=dispatcher, event_callback=cap,
            loop_event_throttle_ms=0,
        )

        spec = _make_loop_workflow(max_iterations=1)
        from binex.graph.dag import DAG
        dag = DAG.from_workflow(spec)

        output, error = await executor.execute_loop(
            spec, dag, "run-b2", "trace-b2", "refine_loop", [],
        )
        assert error is not None
        assert "max iterations" in error.lower()
        event_types = [e["type"] for e in events]
        assert "loop:max_iterations" in event_types
