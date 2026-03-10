"""Tests for per-node budget logic in orchestrator."""

import asyncio
from unittest.mock import patch

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import BudgetConfig, CostRecord, ExecutionResult
from binex.models.execution import RunSummary
from binex.models.task import RetryPolicy
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


class TestPreCheckNodeBudget:
    def test_pre_check_stop_skips_retry_when_budget_exhausted(self):
        """With policy=stop, retry should not run if budget is exhausted."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "flaky": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    budget=1.00,
                    retry_policy=RetryPolicy(max_retries=3),
                ),
            },
        )

        call_count = 0

        async def mock_dispatch(task, inputs, trace_id):
            nonlocal call_count
            call_count += 1
            cost = CostRecord(
                id=f"cr_flaky_{call_count}",
                run_id=task.run_id,
                task_id="flaky",
                cost=0.90,
                source="llm_tokens",
            )
            await exec_store.record_cost(cost)
            raise RuntimeError("temporary failure")

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        # Attempt 1: $0.90 spent, remaining $0.10 > 0, pre-check passes
        # Attempt 2: $0.90 more ($1.80 total), remaining -$0.80, pre-check blocks attempt 3
        assert call_count == 2
        assert summary.status == "failed"

    def test_pre_check_warn_user_declines_retry(self):
        """With policy=warn, user declining should stop retry."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "flaky": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    budget=1.00,
                    retry_policy=RetryPolicy(max_retries=3),
                ),
            },
            budget=BudgetConfig(max_cost=100.0, policy="warn"),
        )

        call_count = 0

        async def mock_dispatch(task, inputs, trace_id):
            nonlocal call_count
            call_count += 1
            cost = CostRecord(
                id=f"cr_flaky_{call_count}",
                run_id=task.run_id,
                task_id="flaky",
                cost=0.90,
                source="llm_tokens",
            )
            await exec_store.record_cost(cost)
            raise RuntimeError("temporary failure")

        with (
            patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch),
            patch("binex.runtime.orchestrator.click.confirm", return_value=False),
        ):
            summary = asyncio.run(orch.run_workflow(spec))

        # Attempt 1: $0.90 spent, remaining $0.10 > 0, pre-check passes
        # Attempt 2: $0.90 more ($1.80 total), remaining -$0.80, user declines
        assert call_count == 2
        assert summary.status == "failed"

    def test_pre_check_warn_user_accepts_retry(self):
        """With policy=warn, user accepting should continue retry."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "flaky": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    budget=1.00,
                    retry_policy=RetryPolicy(max_retries=3),
                ),
            },
            budget=BudgetConfig(max_cost=100.0, policy="warn"),
        )

        call_count = 0

        async def mock_dispatch(task, inputs, trace_id):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                cost = CostRecord(
                    id=f"cr_flaky_{call_count}",
                    run_id=task.run_id,
                    task_id="flaky",
                    cost=0.90,
                    source="llm_tokens",
                )
                await exec_store.record_cost(cost)
                raise RuntimeError("temporary failure")
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="ok",
                                    lineage=Lineage(produced_by="flaky"))],
                cost=CostRecord(
                    id="cr_flaky_2_ok",
                    run_id=task.run_id,
                    task_id="flaky",
                    cost=0.50,
                    source="llm_tokens",
                ),
            )

        with (
            patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch),
            patch("binex.runtime.orchestrator.click.confirm", return_value=True),
        ):
            summary = asyncio.run(orch.run_workflow(spec))

        assert call_count == 2
        # warn policy: node completed despite exceeding budget (0.90+0.50=1.40 > 1.00)
        assert summary.status == "completed"

    def test_no_budget_retry_handled_by_dispatcher(self):
        """Nodes without budget should pass retry_policy to dispatcher."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "normal": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                    retry_policy=RetryPolicy(max_retries=2),
                ),
            },
        )

        captured_task = None

        async def mock_dispatch(task, inputs, trace_id):
            nonlocal captured_task
            captured_task = task
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="ok",
                                    lineage=Lineage(produced_by="normal"))],
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        # Retry policy should be passed to dispatcher (not handled by orchestrator)
        assert captured_task.retry_policy is not None
        assert captured_task.retry_policy.max_retries == 2
        assert summary.status == "completed"


class TestOrchestratorSetsNodeBudget:
    def test_cost_record_gets_node_budget(self):
        """Orchestrator should set node_budget on CostRecord when node has budget."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "budgeted": NodeSpec(
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
                                    lineage=Lineage(produced_by="budgeted"))],
                cost=_make_cost_record(task.run_id, "budgeted", 1.00),
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        costs = asyncio.run(exec_store.list_costs(summary.run_id))
        assert len(costs) == 1
        assert costs[0].node_budget == 5.00

    def test_cost_record_no_node_budget_when_not_set(self):
        """CostRecord should have node_budget=None when node has no budget."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, exec_store)

        spec = WorkflowSpec(
            name="t",
            nodes={
                "unbounded": NodeSpec(
                    agent="local://echo",
                    outputs=["r"],
                ),
            },
        )

        async def mock_dispatch(task, inputs, trace_id):
            return ExecutionResult(
                artifacts=[Artifact(id="a1", run_id=task.run_id,
                                    type="r", content="data",
                                    lineage=Lineage(produced_by="unbounded"))],
                cost=_make_cost_record(task.run_id, "unbounded", 1.00),
            )

        with patch.object(orch.dispatcher, "dispatch", side_effect=mock_dispatch):
            summary = asyncio.run(orch.run_workflow(spec))

        costs = asyncio.run(exec_store.list_costs(summary.run_id))
        assert len(costs) == 1
        assert costs[0].node_budget is None


class TestCostShowNodeBudget:
    def test_text_output_shows_node_budget(self):
        """cost show should display per-node budget info."""
        import json as json_mod
        from unittest.mock import AsyncMock

        from binex.cli.cost import cost_show_cmd
        from binex.models.cost import RunCostSummary
        from click.testing import CliRunner

        mock_summary = RunCostSummary(
            run_id="run_1",
            total_cost=3.00,
            node_costs={"cheap": 0.30, "expensive": 2.70},
        )
        mock_run = RunSummary(
            run_id="run_1", workflow_name="t", status="completed", total_nodes=2,
        )
        mock_costs = [
            CostRecord(id="c1", run_id="run_1", task_id="cheap",
                       cost=0.30, source="llm_tokens", node_budget=0.50),
            CostRecord(id="c2", run_id="run_1", task_id="expensive",
                       cost=2.70, source="llm_tokens"),
        ]

        store = AsyncMock()
        store.get_run = AsyncMock(return_value=mock_run)
        store.get_run_cost_summary = AsyncMock(return_value=mock_summary)
        store.list_costs = AsyncMock(return_value=mock_costs)
        store.close = AsyncMock()

        runner = CliRunner()
        with patch("binex.cli.cost._get_stores", return_value=(store, AsyncMock())):
            result = runner.invoke(cost_show_cmd, ["run_1"])

        assert result.exit_code == 0
        assert "cheap" in result.output
        assert "budget: $0.50" in result.output
        assert "remaining: $0.20" in result.output
        # expensive has no node_budget, should not show budget info
        assert "expensive" in result.output

    def test_json_output_includes_node_budget(self):
        """cost show --json should include node_budget field."""
        import json as json_mod
        from unittest.mock import AsyncMock

        from binex.cli.cost import cost_show_cmd
        from binex.models.cost import RunCostSummary
        from click.testing import CliRunner

        mock_summary = RunCostSummary(
            run_id="run_1",
            total_cost=1.00,
            node_costs={"cheap": 1.00},
        )
        mock_run = RunSummary(
            run_id="run_1", workflow_name="t", status="completed", total_nodes=1,
        )
        mock_costs = [
            CostRecord(id="c1", run_id="run_1", task_id="cheap",
                       cost=1.00, source="llm_tokens", node_budget=2.00),
        ]

        store = AsyncMock()
        store.get_run = AsyncMock(return_value=mock_run)
        store.get_run_cost_summary = AsyncMock(return_value=mock_summary)
        store.list_costs = AsyncMock(return_value=mock_costs)
        store.close = AsyncMock()

        runner = CliRunner()
        with patch("binex.cli.cost._get_stores", return_value=(store, AsyncMock())):
            result = runner.invoke(cost_show_cmd, ["run_1", "--json"])

        assert result.exit_code == 0
        data = json_mod.loads(result.output)
        assert data["nodes"][0]["node_budget"] == 2.00
