"""Tests for budget enforcement in the orchestrator."""

from __future__ import annotations

import logging
import uuid

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import BudgetConfig, CostRecord, ExecutionResult
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


# ---------------------------------------------------------------------------
# Helper: mock adapter that returns a fixed cost per execution
# ---------------------------------------------------------------------------

class CostMockAdapter:
    """Adapter that returns ExecutionResult with a known cost."""

    def __init__(self, cost: float) -> None:
        self._cost = cost

    async def execute(self, task, input_artifacts, trace_id):
        art = Artifact(
            id=f"art_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            type="result",
            content="mock output",
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


# ---------------------------------------------------------------------------
# Helpers: workflow builders
# ---------------------------------------------------------------------------

def _three_node_workflow(
    budget: BudgetConfig | None = None,
) -> WorkflowSpec:
    """Create A -> B -> C sequential workflow with optional budget."""
    return WorkflowSpec(
        name="budget-test",
        nodes={
            "A": NodeSpec(agent="mock://cost", outputs=["result"]),
            "B": NodeSpec(agent="mock://cost", outputs=["result"], depends_on=["A"]),
            "C": NodeSpec(agent="mock://cost", outputs=["result"], depends_on=["B"]),
        },
        budget=budget,
    )


def _make_orchestrator(
    cost_per_node: float,
) -> tuple[Orchestrator, InMemoryExecutionStore, InMemoryArtifactStore]:
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    orch = Orchestrator(artifact_store=art_store, execution_store=exec_store)
    adapter = CostMockAdapter(cost=cost_per_node)
    orch.dispatcher.register_adapter("mock://cost", adapter)
    return orch, exec_store, art_store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBudgetPolicyStop:
    """Budget enforcement with policy=stop."""

    @pytest.mark.asyncio
    async def test_stops_after_budget_exceeded(self):
        """After A ($0.30) and B ($0.60 total), budget ($0.50) is exceeded.
        Node C should be skipped. Run status should be 'over_budget'."""
        budget = BudgetConfig(max_cost=0.50, policy="stop")
        workflow = _three_node_workflow(budget=budget)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.30)

        summary = await orch.run_workflow(workflow)

        assert summary.status == "over_budget"
        assert summary.completed_nodes == 2  # A and B completed
        assert summary.skipped_nodes == 1    # C skipped
        assert summary.total_cost == pytest.approx(0.60)

    @pytest.mark.asyncio
    async def test_skipped_node_not_executed(self):
        """The skipped node should have no execution record or cost record."""
        budget = BudgetConfig(max_cost=0.50, policy="stop")
        workflow = _three_node_workflow(budget=budget)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.30)

        summary = await orch.run_workflow(workflow)

        costs = await exec_store.list_costs(summary.run_id)
        cost_task_ids = {c.task_id for c in costs}
        assert "C" not in cost_task_ids
        assert "A" in cost_task_ids
        assert "B" in cost_task_ids

    @pytest.mark.asyncio
    async def test_first_node_exceeds_budget(self):
        """If even the first node's cost exceeds the budget, the remaining
        nodes should be skipped and status should be 'over_budget'."""
        budget = BudgetConfig(max_cost=0.10, policy="stop")
        workflow = _three_node_workflow(budget=budget)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.50)

        summary = await orch.run_workflow(workflow)

        assert summary.status == "over_budget"
        assert summary.completed_nodes == 1  # A completed before check
        assert summary.skipped_nodes == 2    # B and C skipped


class TestBudgetPolicyWarn:
    """Budget enforcement with policy=warn."""

    @pytest.mark.asyncio
    async def test_warn_continues_execution(self):
        """With policy=warn, all nodes should execute even if budget is exceeded."""
        budget = BudgetConfig(max_cost=0.50, policy="warn")
        workflow = _three_node_workflow(budget=budget)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.30)

        summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 3
        assert summary.skipped_nodes == 0
        assert summary.total_cost == pytest.approx(0.90)

    @pytest.mark.asyncio
    async def test_warn_logs_warning(self, caplog):
        """With policy=warn, a warning should be logged when budget is exceeded."""
        budget = BudgetConfig(max_cost=0.50, policy="warn")
        workflow = _three_node_workflow(budget=budget)
        orch, _, _ = _make_orchestrator(cost_per_node=0.30)

        with caplog.at_level(logging.WARNING, logger="binex.runtime.orchestrator"):
            await orch.run_workflow(workflow)

        budget_warnings = [r for r in caplog.records if "Budget exceeded" in r.message]
        assert len(budget_warnings) >= 1


class TestNoBudget:
    """No budget defined — no enforcement."""

    @pytest.mark.asyncio
    async def test_no_budget_all_nodes_execute(self):
        """Without a budget, all nodes should execute normally."""
        workflow = _three_node_workflow(budget=None)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.30)

        summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 3
        assert summary.skipped_nodes == 0

    @pytest.mark.asyncio
    async def test_no_budget_cost_still_tracked(self):
        """Even without a budget, costs should still be recorded."""
        workflow = _three_node_workflow(budget=None)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.25)

        summary = await orch.run_workflow(workflow)

        costs = await exec_store.list_costs(summary.run_id)
        assert len(costs) == 3
        assert summary.total_cost == pytest.approx(0.75)


class TestBudgetEdgeCases:
    """Edge cases for budget enforcement."""

    @pytest.mark.asyncio
    async def test_cost_exactly_equal_to_max_is_allowed(self):
        """When accumulated cost == max_cost, it is NOT over budget.
        The condition is strictly greater-than (>), not >=."""
        # 3 nodes at $0.10 each = $0.30 total, budget = $0.30
        budget = BudgetConfig(max_cost=0.30, policy="stop")
        workflow = _three_node_workflow(budget=budget)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.10)

        summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 3
        assert summary.skipped_nodes == 0
        assert summary.total_cost == pytest.approx(0.30)

    @pytest.mark.asyncio
    async def test_zero_cost_nodes_never_trigger_budget(self):
        """Nodes with zero cost should never trigger budget enforcement."""
        budget = BudgetConfig(max_cost=0.01, policy="stop")
        workflow = _three_node_workflow(budget=budget)
        orch, _, _ = _make_orchestrator(cost_per_node=0.0)

        summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 3


class TestCostRecording:
    """Orchestrator records CostRecord after each node execution."""

    @pytest.mark.asyncio
    async def test_cost_record_per_node(self):
        """Each node execution should produce exactly one CostRecord."""
        workflow = _three_node_workflow(budget=None)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.15)

        summary = await orch.run_workflow(workflow)

        costs = await exec_store.list_costs(summary.run_id)
        assert len(costs) == 3

        task_ids = [c.task_id for c in costs]
        assert "A" in task_ids
        assert "B" in task_ids
        assert "C" in task_ids

    @pytest.mark.asyncio
    async def test_cost_record_fields(self):
        """CostRecord should carry correct run_id, cost, and source."""
        workflow = _three_node_workflow(budget=None)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.42)

        summary = await orch.run_workflow(workflow)

        costs = await exec_store.list_costs(summary.run_id)
        for cr in costs:
            assert cr.run_id == summary.run_id
            assert cr.cost == pytest.approx(0.42)
            assert cr.source == "llm_tokens"
            assert cr.id.startswith("cost_")


class TestCostAccumulation:
    """Cost accumulates correctly across multiple nodes."""

    @pytest.mark.asyncio
    async def test_total_cost_accumulates(self):
        """Total cost in RunSummary should equal sum of all node costs."""
        workflow = _three_node_workflow(budget=None)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.33)

        summary = await orch.run_workflow(workflow)

        assert summary.total_cost == pytest.approx(0.99)

    @pytest.mark.asyncio
    async def test_cost_summary_node_breakdown(self):
        """get_run_cost_summary should provide per-node cost breakdown."""
        workflow = _three_node_workflow(budget=None)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.20)

        summary = await orch.run_workflow(workflow)

        cost_summary = await exec_store.get_run_cost_summary(summary.run_id)
        assert cost_summary.total_cost == pytest.approx(0.60)
        assert cost_summary.node_costs["A"] == pytest.approx(0.20)
        assert cost_summary.node_costs["B"] == pytest.approx(0.20)
        assert cost_summary.node_costs["C"] == pytest.approx(0.20)

    @pytest.mark.asyncio
    async def test_partial_run_cost_correct_on_stop(self):
        """When budget stops the run, total_cost should reflect only executed nodes."""
        budget = BudgetConfig(max_cost=0.50, policy="stop")
        workflow = _three_node_workflow(budget=budget)
        orch, exec_store, _ = _make_orchestrator(cost_per_node=0.30)

        summary = await orch.run_workflow(workflow)

        cost_summary = await exec_store.get_run_cost_summary(summary.run_id)
        assert cost_summary.total_cost == pytest.approx(0.60)
        assert "C" not in cost_summary.node_costs
