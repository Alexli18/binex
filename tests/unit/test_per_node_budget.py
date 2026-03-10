"""Tests for per-node budget logic in orchestrator."""

import asyncio
from unittest.mock import patch

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import BudgetConfig, CostRecord, ExecutionResult
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator, get_effective_policy, get_node_max_cost
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


class TestGetEffectivePolicy:
    def test_inherits_workflow_stop(self):
        spec = WorkflowSpec(
            name="t",
            nodes={"a": NodeSpec(agent="local://echo", outputs=["r"])},
            budget=BudgetConfig(max_cost=10.0, policy="stop"),
        )
        assert get_effective_policy(spec) == "stop"

    def test_inherits_workflow_warn(self):
        spec = WorkflowSpec(
            name="t",
            nodes={"a": NodeSpec(agent="local://echo", outputs=["r"])},
            budget=BudgetConfig(max_cost=10.0, policy="warn"),
        )
        assert get_effective_policy(spec) == "warn"

    def test_defaults_to_stop_without_workflow_budget(self):
        spec = WorkflowSpec(
            name="t",
            nodes={"a": NodeSpec(agent="local://echo", outputs=["r"])},
        )
        assert get_effective_policy(spec) == "stop"


class TestGetNodeMaxCost:
    def test_no_node_budget_returns_none(self):
        node = NodeSpec(agent="local://echo", outputs=["r"])
        spec = WorkflowSpec(name="t", nodes={"a": node})
        assert get_node_max_cost(node, spec, 0.0) is None

    def test_node_budget_only(self):
        node = NodeSpec(agent="local://echo", outputs=["r"], budget=2.0)
        spec = WorkflowSpec(name="t", nodes={"a": node})
        assert get_node_max_cost(node, spec, 0.0) == 2.0

    def test_node_budget_with_workflow_takes_min(self):
        node = NodeSpec(agent="local://echo", outputs=["r"], budget=5.0)
        spec = WorkflowSpec(
            name="t",
            nodes={"a": node},
            budget=BudgetConfig(max_cost=10.0, policy="stop"),
        )
        assert get_node_max_cost(node, spec, 7.0) == 3.0

    def test_node_budget_smaller_than_remaining(self):
        node = NodeSpec(agent="local://echo", outputs=["r"], budget=1.0)
        spec = WorkflowSpec(
            name="t",
            nodes={"a": node},
            budget=BudgetConfig(max_cost=10.0, policy="stop"),
        )
        assert get_node_max_cost(node, spec, 2.0) == 1.0

    def test_negative_remaining_workflow(self):
        node = NodeSpec(agent="local://echo", outputs=["r"], budget=5.0)
        spec = WorkflowSpec(
            name="t",
            nodes={"a": node},
            budget=BudgetConfig(max_cost=10.0, policy="stop"),
        )
        result = get_node_max_cost(node, spec, 12.0)
        assert result < 0


def _make_cost_record(run_id: str, task_id: str, cost: float) -> CostRecord:
    return CostRecord(
        id=f"cr_{task_id}",
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        source="llm_tokens",
    )


class TestPostCheckNodeBudget:
    def test_post_check_stop_exceeds_node_budget_marks_failed(self):
        """Node exceeding its budget with policy=stop should be marked failed."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "expensive": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    budget=1.00,
                ),
            },
        )

        async def mock_dispatch(task, inputs, trace_id):
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="data",
                                    lineage=Lineage(produced_by="expensive"))],
                cost=_make_cost_record(task.run_id, "expensive", 2.50),
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        assert summary.status == "failed"
        assert summary.failed_nodes == 1

    def test_post_check_warn_exceeds_node_budget_succeeds(self):
        """Node exceeding its budget with policy=warn should succeed."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "expensive": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    budget=1.00,
                ),
            },
            budget=BudgetConfig(max_cost=100.0, policy="warn"),
        )

        async def mock_dispatch(task, inputs, trace_id):
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="data",
                                    lineage=Lineage(produced_by="expensive"))],
                cost=_make_cost_record(task.run_id, "expensive", 2.50),
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        assert summary.status == "completed"
        assert summary.completed_nodes == 1

    def test_post_check_within_budget_succeeds(self):
        """Node within its budget should succeed normally."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "cheap": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    budget=5.00,
                ),
            },
        )

        async def mock_dispatch(task, inputs, trace_id):
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="data",
                                    lineage=Lineage(produced_by="cheap"))],
                cost=_make_cost_record(task.run_id, "cheap", 1.00),
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        assert summary.status == "completed"
        assert summary.completed_nodes == 1

    def test_post_check_no_budget_no_check(self):
        """Node without budget should not trigger any check."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "any": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                ),
            },
        )

        async def mock_dispatch(task, inputs, trace_id):
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="data",
                                    lineage=Lineage(produced_by="any"))],
                cost=_make_cost_record(task.run_id, "any", 999.0),
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        assert summary.status == "completed"
