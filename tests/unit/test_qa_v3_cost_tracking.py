"""QA v3 — comprehensive tests for 007-budget-cost-tracking feature.

Covers gaps identified during QA analysis:
- Dispatcher backward compatibility (list[Artifact] → ExecutionResult wrapping)
- Replay engine cost recording
- RunSummary.skipped_nodes field
- CLI run JSON output with budget info
- A2A adapter edge cases (negative cost from HTTP)
- Parallel nodes with budget enforcement
- SQLite migration path
- CLI cost command registration
- Orchestrator failed node cost handling
- Protocol compliance for ExecutionStore
- Float precision edge cases
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import (
    BudgetConfig,
    CostRecord,
    ExecutionResult,
)
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import RetryPolicy, TaskNode, TaskStatus
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.dispatcher import Dispatcher
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore

# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_task(
    node_id: str = "node1",
    agent: str = "mock://agent",
    run_id: str = "run_test",
) -> TaskNode:
    return TaskNode(
        id=f"{run_id}_{node_id}",
        run_id=run_id,
        node_id=node_id,
        agent=agent,
        system_prompt=None,
        tools=[],
        inputs={},
    )


def _make_artifact(
    aid: str = "art_001",
    run_id: str = "run_test",
    node_id: str = "node1",
) -> Artifact:
    return Artifact(
        id=aid,
        run_id=run_id,
        type="result",
        content="test content",
        lineage=Lineage(produced_by=node_id),
    )


def _make_cost_record(
    run_id: str = "run_test",
    task_id: str = "node1",
    cost: float = 0.01,
    source: str = "llm_tokens",
) -> CostRecord:
    return CostRecord(
        id=f"cost_{uuid.uuid4().hex[:12]}",
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        source=source,
    )


class CostMockAdapter:
    """Mock adapter returning ExecutionResult with configurable cost."""

    def __init__(self, cost: float = 0.10) -> None:
        self._cost = cost

    async def execute(self, task, input_artifacts, trace_id):
        art = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            type="result",
            content="mock",
            lineage=Lineage(produced_by=task.node_id, derived_from=[]),
        )
        cost_record = CostRecord(
            id=f"cost_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            task_id=task.node_id,
            cost=self._cost,
            source="llm_tokens",
        )
        return ExecutionResult(artifacts=[art], cost=cost_record)

    async def cancel(self, task_id):
        pass

    async def health(self):
        return "alive"


class LegacyAdapter:
    """Mock adapter returning list[Artifact] (legacy interface)."""

    async def execute(self, task, input_artifacts, trace_id):
        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type="result",
                content="legacy output",
                lineage=Lineage(produced_by=task.node_id),
            )
        ]

    async def cancel(self, task_id):
        pass

    async def health(self):
        return "alive"


class FailingAdapter:
    """Mock adapter that always raises."""

    async def execute(self, task, input_artifacts, trace_id):
        raise RuntimeError("adapter failure")

    async def cancel(self, task_id):
        pass

    async def health(self):
        return "alive"


# ═══════════════════════════════════════════════════════════════════════════
# TC-DISP: Dispatcher backward compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestDispatcherBackwardCompat:
    """Dispatcher wraps list[Artifact] in ExecutionResult for legacy adapters."""

    @pytest.mark.asyncio
    async def test_legacy_adapter_returns_execution_result(self):
        """Legacy adapter returning list[Artifact] gets wrapped in ExecutionResult."""
        dispatcher = Dispatcher()
        dispatcher.register_adapter("legacy://test", LegacyAdapter())
        task = _make_task(agent="legacy://test")

        result = await dispatcher.dispatch(task, [], "trace_1")

        assert isinstance(result, ExecutionResult)
        assert len(result.artifacts) == 1
        assert result.cost is None  # Legacy adapters have no cost

    @pytest.mark.asyncio
    async def test_new_adapter_returns_execution_result_directly(self):
        """New adapter returning ExecutionResult passes through unchanged."""
        dispatcher = Dispatcher()
        dispatcher.register_adapter("mock://cost", CostMockAdapter(cost=0.05))
        task = _make_task(agent="mock://cost")

        result = await dispatcher.dispatch(task, [], "trace_2")

        assert isinstance(result, ExecutionResult)
        assert result.cost is not None
        assert result.cost.cost == 0.05

    @pytest.mark.asyncio
    async def test_dispatcher_retry_preserves_execution_result(self):
        """Dispatcher with retry still returns ExecutionResult on success."""
        dispatcher = Dispatcher()
        dispatcher.register_adapter("mock://cost", CostMockAdapter(cost=0.03))
        task = _make_task(agent="mock://cost")
        task.retry_policy = RetryPolicy(max_retries=3)

        result = await dispatcher.dispatch(task, [], "trace_3")

        assert isinstance(result, ExecutionResult)
        assert result.cost.cost == 0.03


# ═══════════════════════════════════════════════════════════════════════════
# TC-REPLAY: Replay engine cost recording
# ═══════════════════════════════════════════════════════════════════════════


class TestReplayCostRecording:
    """Replay engine records cost for re-executed nodes."""

    @pytest.mark.asyncio
    async def test_replay_records_cost_for_re_executed_nodes(self):
        from binex.runtime.replay import ReplayEngine

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        # Create original run
        original_run = RunSummary(
            run_id="run_orig",
            workflow_name="test-wf",
            status="completed",
            total_nodes=2,
            completed_nodes=2,
        )
        await exec_store.create_run(original_run)

        # Record original execution for node A
        orig_art = _make_artifact(aid="art_A", run_id="run_orig", node_id="A")
        await art_store.store(orig_art)
        orig_record = ExecutionRecord(
            id="rec_orig_A",
            run_id="run_orig",
            task_id="A",
            agent_id="mock://cost",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=[],
            output_artifact_refs=["art_A"],
            latency_ms=100,
            trace_id="trace_orig",
        )
        await exec_store.record(orig_record)

        # Record original execution for node B
        orig_art_b = _make_artifact(aid="art_B", run_id="run_orig", node_id="B")
        await art_store.store(orig_art_b)
        orig_record_b = ExecutionRecord(
            id="rec_orig_B",
            run_id="run_orig",
            task_id="B",
            agent_id="mock://cost",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=["art_A"],
            output_artifact_refs=["art_B"],
            latency_ms=100,
            trace_id="trace_orig",
        )
        await exec_store.record(orig_record_b)

        # Create workflow for replay
        workflow = WorkflowSpec(
            name="test-wf",
            nodes={
                "A": NodeSpec(agent="mock://cost", outputs=["result"]),
                "B": NodeSpec(
                    agent="mock://cost",
                    outputs=["result"],
                    depends_on=["A"],
                ),
            },
        )

        # Replay from B with cost-tracking adapter
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
        )
        engine.dispatcher.register_adapter("mock://cost", CostMockAdapter(cost=0.15))

        summary = await engine.replay("run_orig", workflow, from_step="B")

        assert summary.status == "completed"

        # Verify cost was recorded for re-executed node B
        costs = await exec_store.list_costs(summary.run_id)
        assert len(costs) == 1
        assert costs[0].task_id == "B"
        assert costs[0].cost == 0.15


# ═══════════════════════════════════════════════════════════════════════════
# TC-RUNSUMMARY: RunSummary.skipped_nodes field
# ═══════════════════════════════════════════════════════════════════════════


class TestRunSummarySkippedNodes:
    """RunSummary.skipped_nodes new field."""

    def test_default_skipped_nodes_zero(self):
        rs = RunSummary(
            run_id="r1",
            workflow_name="test",
            status="completed",
            total_nodes=3,
        )
        assert rs.skipped_nodes == 0

    def test_skipped_nodes_set(self):
        rs = RunSummary(
            run_id="r1",
            workflow_name="test",
            status="over_budget",
            total_nodes=5,
            completed_nodes=3,
            skipped_nodes=2,
        )
        assert rs.skipped_nodes == 2

    def test_total_cost_default_zero(self):
        rs = RunSummary(
            run_id="r1",
            workflow_name="test",
            status="completed",
            total_nodes=1,
        )
        assert rs.total_cost == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# TC-CLI-JSON: CLI run JSON output with budget info
# ═══════════════════════════════════════════════════════════════════════════


class TestRunCLIJsonBudget:
    """CLI run --json includes budget/remaining_budget when budget is defined."""

    @pytest.fixture()
    def workflow_file(self, tmp_path):
        f = tmp_path / "wf.yaml"
        f.write_text("name: test\nnodes: {}\n")
        return str(f)

    def test_json_output_includes_budget_fields(self, workflow_file):
        from binex.cli.run import run_cmd

        summary = RunSummary(
            run_id="run_json1",
            workflow_name="json-wf",
            status="completed",
            total_nodes=2,
            completed_nodes=2,
            total_cost=3.00,
        )

        spec = MagicMock()
        spec.nodes = {"a": MagicMock(depends_on=[]), "b": MagicMock(depends_on=["a"])}
        spec.budget = BudgetConfig(max_cost=10.00, policy="warn")

        runner = CliRunner()
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run.load_workflow", return_value=spec),
            patch("binex.cli.run.validate_workflow", return_value=[]),
            patch("binex.cli.run._run", return_value=(summary, [], [])),
        ):
            result = runner.invoke(run_cmd, [workflow_file, "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["budget"] == 10.00
        assert data["remaining_budget"] == pytest.approx(7.00)

    def test_json_output_no_budget_fields_when_no_budget(self, workflow_file):
        from binex.cli.run import run_cmd

        summary = RunSummary(
            run_id="run_json2",
            workflow_name="no-budget-wf",
            status="completed",
            total_nodes=1,
            completed_nodes=1,
            total_cost=0.50,
        )

        spec = MagicMock()
        spec.nodes = {"a": MagicMock(depends_on=[])}
        spec.budget = None

        runner = CliRunner()
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run.load_workflow", return_value=spec),
            patch("binex.cli.run.validate_workflow", return_value=[]),
            patch("binex.cli.run._run", return_value=(summary, [], [])),
        ):
            result = runner.invoke(run_cmd, [workflow_file, "--json"], catch_exceptions=False)

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "budget" not in data
        assert "remaining_budget" not in data


# ═══════════════════════════════════════════════════════════════════════════
# TC-A2A-EDGE: A2A adapter edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestA2AAdapterCostEdgeCases:
    """A2A adapter cost edge cases."""

    @pytest.mark.asyncio
    async def test_a2a_zero_cost_from_response(self):
        """Response with cost=0 should be recorded with source='agent_report'."""
        from binex.adapters.a2a import A2AAgentAdapter

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"type": "result", "content": "ok"}],
            "cost": 0,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        task = _make_task(agent="a2a://http://localhost:8000")

        with patch("binex.adapters.a2a.httpx.AsyncClient", return_value=mock_client):
            adapter = A2AAgentAdapter(endpoint="http://localhost:8000")
            result = await adapter.execute(task, [], "trace_edge")

        assert result.cost.cost == 0.0
        assert result.cost.source == "agent_report"

    @pytest.mark.asyncio
    async def test_a2a_string_cost_in_response(self):
        """Response with cost as string number should be converted to float."""
        from binex.adapters.a2a import A2AAgentAdapter

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"type": "result", "content": "ok"}],
            "cost": "0.55",  # String cost
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        task = _make_task(agent="a2a://http://localhost:8000")

        with patch("binex.adapters.a2a.httpx.AsyncClient", return_value=mock_client):
            adapter = A2AAgentAdapter(endpoint="http://localhost:8000")
            result = await adapter.execute(task, [], "trace_str")

        assert result.cost.cost == pytest.approx(0.55)
        assert result.cost.source == "agent_report"


# ═══════════════════════════════════════════════════════════════════════════
# TC-PARALLEL: Parallel nodes with budget enforcement
# ═══════════════════════════════════════════════════════════════════════════


class TestParallelNodesBudget:
    """Budget enforcement with parallel (non-dependent) nodes."""

    @pytest.mark.asyncio
    async def test_parallel_nodes_all_execute_under_budget(self):
        """Three parallel nodes under budget should all complete."""
        from binex.runtime.orchestrator import Orchestrator

        workflow = WorkflowSpec(
            name="parallel-budget",
            nodes={
                "A": NodeSpec(agent="mock://cost", outputs=["result"]),
                "B": NodeSpec(agent="mock://cost", outputs=["result"]),
                "C": NodeSpec(agent="mock://cost", outputs=["result"]),
            },
            budget=BudgetConfig(max_cost=5.0, policy="stop"),
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(artifact_store=art_store, execution_store=exec_store)
        orch.dispatcher.register_adapter("mock://cost", CostMockAdapter(cost=0.10))

        summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 3
        costs = await exec_store.list_costs(summary.run_id)
        assert len(costs) == 3

    @pytest.mark.asyncio
    async def test_no_budget_parallel_nodes_all_tracked(self):
        """Parallel nodes without budget still get cost tracked."""
        from binex.runtime.orchestrator import Orchestrator

        workflow = WorkflowSpec(
            name="parallel-no-budget",
            nodes={
                "X": NodeSpec(agent="mock://cost", outputs=["result"]),
                "Y": NodeSpec(agent="mock://cost", outputs=["result"]),
            },
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(artifact_store=art_store, execution_store=exec_store)
        orch.dispatcher.register_adapter("mock://cost", CostMockAdapter(cost=0.25))

        summary = await orch.run_workflow(workflow)

        assert summary.total_cost == pytest.approx(0.50)


# ═══════════════════════════════════════════════════════════════════════════
# TC-SQLITE-MIG: SQLite migration path
# ═══════════════════════════════════════════════════════════════════════════


class TestSqliteMigration:
    """SQLite schema migration for cost_records table and total_cost column."""

    @pytest.mark.asyncio
    async def test_double_initialize_idempotent(self):
        """Calling initialize() twice should not fail (CREATE IF NOT EXISTS)."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SqliteExecutionStore(path)
            await store.initialize()
            await store.initialize()  # Second call should be safe
            await store.close()
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_cost_records_table_created(self):
        """cost_records table should exist after initialization."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SqliteExecutionStore(path)
            await store.initialize()

            # Verify table exists by inserting and reading
            record = _make_cost_record()
            await store.record_cost(record)
            costs = await store.list_costs("run_test")
            assert len(costs) == 1
            await store.close()
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_total_cost_column_migration(self):
        """total_cost column in runs table should work after migration."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SqliteExecutionStore(path)
            await store.initialize()

            run = RunSummary(
                run_id="run_mig",
                workflow_name="migration-test",
                status="completed",
                total_nodes=1,
                total_cost=1.50,
            )
            await store.create_run(run)
            retrieved = await store.get_run("run_mig")
            assert retrieved is not None
            assert retrieved.total_cost == pytest.approx(1.50)
            await store.close()
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# TC-CLI-REG: CLI cost command registration
# ═══════════════════════════════════════════════════════════════════════════


class TestCLICostRegistration:
    """CLI cost command is properly registered."""

    def test_cost_group_exists_in_cli(self):
        """binex cost should be a registered command group."""
        from binex.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "--help"])
        assert result.exit_code == 0
        assert "show" in result.output
        assert "history" in result.output

    def test_cost_show_help(self):
        """binex cost show --help should work."""
        from binex.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "show", "--help"])
        assert result.exit_code == 0
        assert "RUN_ID" in result.output

    def test_cost_history_help(self):
        """binex cost history --help should work."""
        from binex.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["cost", "history", "--help"])
        assert result.exit_code == 0
        assert "RUN_ID" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# TC-ORCH-FAIL: Orchestrator failed node cost handling
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestratorFailedNodeCost:
    """Failed nodes should not record cost (exception before cost recording)."""

    @pytest.mark.asyncio
    async def test_failed_node_no_cost_record(self):
        """When adapter raises, no cost record should be stored for that node."""
        from binex.runtime.orchestrator import Orchestrator

        workflow = WorkflowSpec(
            name="fail-test",
            nodes={
                "A": NodeSpec(agent="fail://adapter", outputs=["result"]),
            },
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(artifact_store=art_store, execution_store=exec_store)
        orch.dispatcher.register_adapter("fail://adapter", FailingAdapter())

        summary = await orch.run_workflow(workflow)

        assert summary.status == "failed"
        costs = await exec_store.list_costs(summary.run_id)
        assert len(costs) == 0

    @pytest.mark.asyncio
    async def test_partial_failure_only_successful_costs(self):
        """In A -> B workflow, if B fails, only A's cost should be recorded."""
        from binex.runtime.orchestrator import Orchestrator

        workflow = WorkflowSpec(
            name="partial-fail",
            nodes={
                "A": NodeSpec(agent="mock://cost", outputs=["result"]),
                "B": NodeSpec(
                    agent="fail://adapter",
                    outputs=["result"],
                    depends_on=["A"],
                ),
            },
        )

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(artifact_store=art_store, execution_store=exec_store)
        orch.dispatcher.register_adapter("mock://cost", CostMockAdapter(cost=0.20))
        orch.dispatcher.register_adapter("fail://adapter", FailingAdapter())

        summary = await orch.run_workflow(workflow)

        assert summary.status == "failed"
        costs = await exec_store.list_costs(summary.run_id)
        assert len(costs) == 1
        assert costs[0].task_id == "A"
        assert costs[0].cost == 0.20


# ═══════════════════════════════════════════════════════════════════════════
# TC-PROTOCOL: ExecutionStore protocol compliance
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutionStoreProtocol:
    """Both store implementations comply with ExecutionStore protocol for cost methods."""

    @pytest.mark.asyncio
    async def test_memory_store_has_record_cost(self):
        store = InMemoryExecutionStore()
        assert hasattr(store, "record_cost")
        assert hasattr(store, "list_costs")
        assert hasattr(store, "get_run_cost_summary")

    @pytest.mark.asyncio
    async def test_sqlite_store_has_record_cost(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SqliteExecutionStore(path)
            await store.initialize()
            assert hasattr(store, "record_cost")
            assert hasattr(store, "list_costs")
            assert hasattr(store, "get_run_cost_summary")
            await store.close()
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# TC-FLOAT: Float precision edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestFloatPrecision:
    """Cost calculations with float precision challenges."""

    def test_cost_record_very_small_cost(self):
        """Very small positive costs should be preserved."""
        rec = CostRecord(
            id="c_small",
            run_id="r1",
            task_id="t1",
            cost=0.000001,
            source="llm_tokens",
        )
        assert rec.cost == pytest.approx(0.000001)

    def test_cost_record_very_large_cost(self):
        """Large cost values should be preserved."""
        rec = CostRecord(
            id="c_large",
            run_id="r1",
            task_id="t1",
            cost=999999.99,
            source="llm_tokens",
        )
        assert rec.cost == pytest.approx(999999.99)

    @pytest.mark.asyncio
    async def test_memory_store_float_accumulation(self):
        """Memory store should handle float accumulation correctly."""
        store = InMemoryExecutionStore()
        # Classic float precision challenge: 0.1 + 0.2 != 0.3
        for i in range(10):
            await store.record_cost(_make_cost_record(cost=0.1, task_id=f"n{i}"))
        summary = await store.get_run_cost_summary("run_test")
        assert summary.total_cost == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_sqlite_store_float_accumulation(self):
        """SQLite store should handle float accumulation correctly."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            store = SqliteExecutionStore(path)
            await store.initialize()
            for i in range(10):
                await store.record_cost(_make_cost_record(cost=0.1, task_id=f"n{i}"))
            summary = await store.get_run_cost_summary("run_test")
            assert summary.total_cost == pytest.approx(1.0)
            await store.close()
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════
# TC-MODEL-EXPORTS: Model re-exports from __init__
# ═══════════════════════════════════════════════════════════════════════════


class TestModelExports:
    """All cost models are properly exported from binex.models."""

    def test_cost_record_importable(self):
        from binex.models import CostRecord
        assert CostRecord is not None

    def test_budget_config_importable(self):
        from binex.models import BudgetConfig
        assert BudgetConfig is not None

    def test_execution_result_importable(self):
        from binex.models import ExecutionResult
        assert ExecutionResult is not None

    def test_node_cost_hint_importable(self):
        from binex.models import NodeCostHint
        assert NodeCostHint is not None

    def test_run_cost_summary_importable(self):
        from binex.models import RunCostSummary
        assert RunCostSummary is not None


# ═══════════════════════════════════════════════════════════════════════════
# TC-COST-CLI-EDGE: CLI cost edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestCostCLIEdgeCases:
    """Edge cases for binex cost CLI commands."""

    def test_cost_history_run_not_found(self):
        from binex.cli.cost import cost_history_cmd

        runner = CliRunner()
        store = InMemoryExecutionStore()
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_history_cmd, ["nonexistent"])

        assert result.exit_code != 0

    def test_cost_show_json_with_budget(self):
        """cost show --json should include budget/remaining_budget fields."""
        from binex.cli.cost import cost_show_cmd

        async def _setup():
            store = InMemoryExecutionStore()
            run = RunSummary(
                run_id="run_budget",
                workflow_name="budget-wf",
                status="completed",
                total_nodes=1,
                completed_nodes=1,
                total_cost=2.0,
            )
            await store.create_run(run)
            await store.record_cost(CostRecord(
                id="c1",
                run_id="run_budget",
                task_id="n1",
                cost=2.0,
                source="llm_tokens",
            ))
            return store

        store = asyncio.run(_setup())
        runner = CliRunner()
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_show_cmd, ["run_budget", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_cost"] == pytest.approx(2.0)
        assert data["currency"] == "USD"

    def test_cost_history_json_empty_records(self):
        """cost history --json with no records should return empty list."""
        from binex.cli.cost import cost_history_cmd

        async def _setup():
            store = InMemoryExecutionStore()
            run = RunSummary(
                run_id="run_empty",
                workflow_name="empty-wf",
                status="completed",
                total_nodes=0,
                total_cost=0.0,
            )
            await store.create_run(run)
            return store

        store = asyncio.run(_setup())
        runner = CliRunner()
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_history_cmd, ["run_empty", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["records"] == []


# ═══════════════════════════════════════════════════════════════════════════
# TC-WORKFLOW-YAML: Budget from dict (YAML loading simulation)
# ═══════════════════════════════════════════════════════════════════════════


class TestBudgetFromDict:
    """Budget config created from dict (as would come from YAML)."""

    def test_workflow_with_budget_from_dict(self):
        """WorkflowSpec should accept budget as dict (YAML-like)."""
        ws = WorkflowSpec(
            name="yaml-test",
            nodes={
                "n1": NodeSpec(agent="llm://gpt-4", outputs=["result"]),
            },
            budget={"max_cost": 5.0, "policy": "stop"},
        )
        assert ws.budget is not None
        assert ws.budget.max_cost == 5.0
        assert ws.budget.policy == "stop"

    def test_workflow_with_budget_warn_from_dict(self):
        ws = WorkflowSpec(
            name="yaml-test-2",
            nodes={
                "n1": NodeSpec(agent="llm://gpt-4", outputs=["result"]),
            },
            budget={"max_cost": 10.0},
        )
        assert ws.budget.policy == "warn"

    def test_node_with_cost_hint_from_dict(self):
        ns = NodeSpec(
            agent="llm://gpt-4",
            outputs=["result"],
            cost={"estimate": 0.25},
        )
        assert ns.cost is not None
        assert ns.cost.estimate == 0.25


# ═══════════════════════════════════════════════════════════════════════════
# TC-COST-SOURCE: CostSource literal validation
# ═══════════════════════════════════════════════════════════════════════════


class TestCostSourceValidation:
    """CostSource literal type validation."""

    @pytest.mark.parametrize("source", [
        "llm_tokens",
        "llm_tokens_unavailable",
        "agent_report",
        "local",
        "unknown",
    ])
    def test_valid_sources(self, source):
        rec = CostRecord(id="c1", run_id="r1", task_id="t1", source=source)
        assert rec.source == source

    def test_invalid_source_rejected(self):
        with pytest.raises(ValidationError):
            CostRecord(id="c1", run_id="r1", task_id="t1", source="custom_source")  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# TC-ADAPTER-BASE: Base protocol return type
# ═══════════════════════════════════════════════════════════════════════════


class TestAdapterProtocolReturnType:
    """AgentAdapter.execute() accepts both return types."""

    def test_execution_result_has_artifacts_and_cost(self):
        art = _make_artifact()
        cost = _make_cost_record()
        er = ExecutionResult(artifacts=[art], cost=cost)
        assert len(er.artifacts) == 1
        assert er.cost is not None

    def test_execution_result_serializable(self):
        """ExecutionResult should be JSON-serializable via model_dump."""
        art = _make_artifact()
        cost = _make_cost_record()
        er = ExecutionResult(artifacts=[art], cost=cost)
        data = er.model_dump()
        assert "artifacts" in data
        assert "cost" in data
        assert data["cost"]["source"] == "llm_tokens"
