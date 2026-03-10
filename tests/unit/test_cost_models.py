"""Comprehensive tests for cost tracking domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import (
    BudgetConfig,
    CostRecord,
    ExecutionResult,
    NodeBudget,
    NodeCostHint,
    RunCostSummary,
)
from binex.models.workflow import NodeSpec, WorkflowSpec


# ---------------------------------------------------------------------------
# CostRecord
# ---------------------------------------------------------------------------

class TestCostRecord:
    def test_minimal_valid(self):
        rec = CostRecord(id="c1", run_id="r1", task_id="t1", source="llm_tokens")
        assert rec.cost == 0.0
        assert rec.currency == "USD"
        assert rec.prompt_tokens is None
        assert rec.completion_tokens is None
        assert rec.model is None
        assert isinstance(rec.timestamp, datetime)

    def test_all_fields(self):
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        rec = CostRecord(
            id="c2",
            run_id="r2",
            task_id="t2",
            cost=0.05,
            currency="EUR",
            source="agent_report",
            prompt_tokens=100,
            completion_tokens=50,
            model="gpt-4",
            timestamp=ts,
        )
        assert rec.cost == 0.05
        assert rec.currency == "EUR"
        assert rec.source == "agent_report"
        assert rec.prompt_tokens == 100
        assert rec.completion_tokens == 50
        assert rec.model == "gpt-4"
        assert rec.timestamp == ts

    def test_cost_zero_is_valid(self):
        rec = CostRecord(id="c3", run_id="r1", task_id="t1", source="local", cost=0.0)
        assert rec.cost == 0.0

    def test_cost_negative_raises(self):
        with pytest.raises(ValidationError, match="cost must be >= 0"):
            CostRecord(id="c4", run_id="r1", task_id="t1", source="local", cost=-0.01)

    def test_missing_required_id(self):
        with pytest.raises(ValidationError):
            CostRecord(run_id="r1", task_id="t1", source="local")  # type: ignore[call-arg]

    def test_missing_required_run_id(self):
        with pytest.raises(ValidationError):
            CostRecord(id="c1", task_id="t1", source="local")  # type: ignore[call-arg]

    def test_missing_required_task_id(self):
        with pytest.raises(ValidationError):
            CostRecord(id="c1", run_id="r1", source="local")  # type: ignore[call-arg]

    def test_missing_required_source(self):
        with pytest.raises(ValidationError):
            CostRecord(id="c1", run_id="r1", task_id="t1")  # type: ignore[call-arg]

    def test_invalid_source_value(self):
        with pytest.raises(ValidationError):
            CostRecord(id="c1", run_id="r1", task_id="t1", source="magic")  # type: ignore[arg-type]

    @pytest.mark.parametrize("source", [
        "llm_tokens",
        "llm_tokens_unavailable",
        "agent_report",
        "local",
        "unknown",
    ])
    def test_all_valid_sources(self, source):
        rec = CostRecord(id="c1", run_id="r1", task_id="t1", source=source)
        assert rec.source == source

    def test_timestamp_default_is_utc(self):
        rec = CostRecord(id="c1", run_id="r1", task_id="t1", source="local")
        assert rec.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# BudgetConfig
# ---------------------------------------------------------------------------

class TestBudgetConfig:
    def test_minimal_valid(self):
        bc = BudgetConfig(max_cost=10.0)
        assert bc.max_cost == 10.0
        assert bc.currency == "USD"
        assert bc.policy == "warn"

    def test_custom_policy_stop(self):
        bc = BudgetConfig(max_cost=5.0, policy="stop")
        assert bc.policy == "stop"

    def test_custom_currency(self):
        bc = BudgetConfig(max_cost=1.0, currency="EUR")
        assert bc.currency == "EUR"

    def test_max_cost_zero_raises(self):
        with pytest.raises(ValidationError, match="max_cost must be > 0"):
            BudgetConfig(max_cost=0.0)

    def test_max_cost_negative_raises(self):
        with pytest.raises(ValidationError, match="max_cost must be > 0"):
            BudgetConfig(max_cost=-5.0)

    def test_max_cost_small_positive(self):
        bc = BudgetConfig(max_cost=0.001)
        assert bc.max_cost == 0.001

    def test_invalid_policy_raises(self):
        with pytest.raises(ValidationError):
            BudgetConfig(max_cost=10.0, policy="ignore")  # type: ignore[arg-type]

    def test_missing_max_cost_raises(self):
        with pytest.raises(ValidationError):
            BudgetConfig()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# NodeCostHint
# ---------------------------------------------------------------------------

class TestNodeCostHint:
    def test_default_estimate(self):
        hint = NodeCostHint()
        assert hint.estimate == 0.0

    def test_positive_estimate(self):
        hint = NodeCostHint(estimate=0.12)
        assert hint.estimate == 0.12

    def test_zero_estimate(self):
        hint = NodeCostHint(estimate=0.0)
        assert hint.estimate == 0.0

    def test_negative_estimate_raises(self):
        with pytest.raises(ValidationError, match="estimate must be >= 0"):
            NodeCostHint(estimate=-0.5)


# ---------------------------------------------------------------------------
# RunCostSummary
# ---------------------------------------------------------------------------

class TestRunCostSummary:
    def test_minimal(self):
        s = RunCostSummary(run_id="r1")
        assert s.run_id == "r1"
        assert s.total_cost == 0.0
        assert s.currency == "USD"
        assert s.budget is None
        assert s.remaining_budget is None
        assert s.node_costs == {}

    def test_with_all_fields(self):
        s = RunCostSummary(
            run_id="r2",
            total_cost=1.23,
            currency="EUR",
            budget=5.0,
            remaining_budget=3.77,
            node_costs={"nodeA": 0.5, "nodeB": 0.73},
        )
        assert s.total_cost == 1.23
        assert s.budget == 5.0
        assert s.remaining_budget == 3.77
        assert s.node_costs == {"nodeA": 0.5, "nodeB": 0.73}

    def test_node_costs_default_is_independent(self):
        a = RunCostSummary(run_id="r1")
        b = RunCostSummary(run_id="r2")
        a.node_costs["x"] = 1.0
        assert "x" not in b.node_costs


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------

def _make_artifact(aid: str = "a1", run_id: str = "r1") -> Artifact:
    return Artifact(
        id=aid,
        run_id=run_id,
        type="text",
        content="hello",
        lineage=Lineage(produced_by="node1"),
    )


class TestExecutionResult:
    def test_without_cost(self):
        art = _make_artifact()
        er = ExecutionResult(artifacts=[art])
        assert len(er.artifacts) == 1
        assert er.cost is None

    def test_with_cost(self):
        art = _make_artifact()
        cost = CostRecord(id="c1", run_id="r1", task_id="t1", source="llm_tokens", cost=0.03)
        er = ExecutionResult(artifacts=[art], cost=cost)
        assert er.cost is not None
        assert er.cost.cost == 0.03

    def test_empty_artifacts(self):
        er = ExecutionResult(artifacts=[])
        assert er.artifacts == []
        assert er.cost is None

    def test_multiple_artifacts(self):
        arts = [_make_artifact(f"a{i}") for i in range(3)]
        er = ExecutionResult(artifacts=arts)
        assert len(er.artifacts) == 3


# ---------------------------------------------------------------------------
# WorkflowSpec — budget section
# ---------------------------------------------------------------------------

def _make_node(**kwargs) -> NodeSpec:
    defaults = {"agent": "llm://gpt-4", "outputs": ["result"]}
    defaults.update(kwargs)
    return NodeSpec(**defaults)


class TestWorkflowSpecBudget:
    def test_without_budget(self):
        ws = WorkflowSpec(
            name="test",
            nodes={"n1": _make_node()},
        )
        assert ws.budget is None

    def test_with_budget(self):
        ws = WorkflowSpec(
            name="test",
            nodes={"n1": _make_node()},
            budget=BudgetConfig(max_cost=10.0, policy="stop"),
        )
        assert ws.budget is not None
        assert ws.budget.max_cost == 10.0
        assert ws.budget.policy == "stop"

    def test_budget_warn_policy(self):
        ws = WorkflowSpec(
            name="test",
            nodes={"n1": _make_node()},
            budget=BudgetConfig(max_cost=2.0),
        )
        assert ws.budget.policy == "warn"

    def test_invalid_budget_policy_raises(self):
        with pytest.raises(ValidationError):
            WorkflowSpec(
                name="test",
                nodes={"n1": _make_node()},
                budget=BudgetConfig(max_cost=10.0, policy="ignore"),  # type: ignore[arg-type]
            )

    def test_budget_zero_max_cost_raises(self):
        with pytest.raises(ValidationError):
            WorkflowSpec(
                name="test",
                nodes={"n1": _make_node()},
                budget=BudgetConfig(max_cost=0),
            )


# ---------------------------------------------------------------------------
# NodeSpec — cost hint
# ---------------------------------------------------------------------------

class TestNodeSpecCostHint:
    def test_no_cost_hint(self):
        node = _make_node()
        assert node.cost is None

    def test_with_cost_hint(self):
        node = _make_node(cost=NodeCostHint(estimate=0.05))
        assert node.cost is not None
        assert node.cost.estimate == 0.05

    def test_cost_hint_negative_raises(self):
        with pytest.raises(ValidationError, match="estimate must be >= 0"):
            _make_node(cost=NodeCostHint(estimate=-1.0))

    def test_cost_hint_from_dict(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["out"], cost={"estimate": 0.1})
        assert node.cost.estimate == 0.1


# ---------------------------------------------------------------------------
# NodeBudget
# ---------------------------------------------------------------------------

class TestNodeBudget:
    def test_valid_node_budget(self):
        nb = NodeBudget(max_cost=1.50)
        assert nb.max_cost == 1.50

    def test_node_budget_rejects_zero(self):
        with pytest.raises(ValidationError):
            NodeBudget(max_cost=0)

    def test_node_budget_rejects_negative(self):
        with pytest.raises(ValidationError):
            NodeBudget(max_cost=-1.0)

    def test_node_budget_accepts_small_float(self):
        nb = NodeBudget(max_cost=0.01)
        assert nb.max_cost == 0.01


# ---------------------------------------------------------------------------
# NodeSpec — budget field
# ---------------------------------------------------------------------------

class TestNodeSpecBudget:
    def test_node_budget_none_by_default(self):
        ns = NodeSpec(agent="local://echo", outputs=["r"])
        assert ns.budget is None

    def test_node_budget_shorthand_float(self):
        ns = NodeSpec(agent="local://echo", outputs=["r"], budget=0.50)
        assert isinstance(ns.budget, NodeBudget)
        assert ns.budget.max_cost == 0.50

    def test_node_budget_shorthand_int(self):
        ns = NodeSpec(agent="local://echo", outputs=["r"], budget=2)
        assert isinstance(ns.budget, NodeBudget)
        assert ns.budget.max_cost == 2.0

    def test_node_budget_full_form(self):
        ns = NodeSpec(agent="local://echo", outputs=["r"], budget={"max_cost": 3.00})
        assert isinstance(ns.budget, NodeBudget)
        assert ns.budget.max_cost == 3.00

    def test_node_budget_in_workflow_yaml(self):
        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(agent="local://echo", outputs=["r"], budget=1.00),
                "b": NodeSpec(agent="local://echo", outputs=["r"], budget={"max_cost": 2.00}),
                "c": NodeSpec(agent="local://echo", outputs=["r"]),
            },
        )
        assert spec.nodes["a"].budget.max_cost == 1.00
        assert spec.nodes["b"].budget.max_cost == 2.00
        assert spec.nodes["c"].budget is None

    def test_node_budget_rejects_zero_shorthand(self):
        with pytest.raises(ValidationError):
            NodeSpec(agent="local://echo", outputs=["r"], budget=0)

    def test_node_budget_rejects_negative_shorthand(self):
        with pytest.raises(ValidationError):
            NodeSpec(agent="local://echo", outputs=["r"], budget=-1.0)
