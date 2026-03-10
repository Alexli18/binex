"""Tests for per-node budget logic in orchestrator."""

import pytest

from binex.models.cost import BudgetConfig, NodeBudget
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import get_effective_policy, get_node_max_cost


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
