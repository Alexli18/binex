"""Tests for cost CLI commands and run command cost output."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.cli.cost import cost_history_cmd, cost_show_cmd
from binex.models.cost import CostRecord
from binex.models.execution import RunSummary
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_stores_with_costs() -> InMemoryExecutionStore:
    """Create and populate an InMemoryExecutionStore with test cost data."""

    async def _setup():
        store = InMemoryExecutionStore()
        run = RunSummary(
            run_id="run_test123",
            workflow_name="test-wf",
            status="completed",
            total_nodes=2,
            completed_nodes=2,
            total_cost=0.83,
        )
        await store.create_run(run)

        await store.record_cost(CostRecord(
            id="cost_001",
            run_id="run_test123",
            task_id="planner",
            cost=0.33,
            source="llm_tokens",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=50,
        ))
        await store.record_cost(CostRecord(
            id="cost_002",
            run_id="run_test123",
            task_id="researcher",
            cost=0.50,
            source="llm_tokens",
            model="gpt-4",
            prompt_tokens=200,
            completion_tokens=100,
        ))
        return store

    return asyncio.run(_setup())


def _make_stores_no_costs() -> InMemoryExecutionStore:
    """Create store with a run but no cost records."""

    async def _setup():
        store = InMemoryExecutionStore()
        run = RunSummary(
            run_id="run_empty",
            workflow_name="empty-wf",
            status="completed",
            total_nodes=1,
            completed_nodes=1,
            total_cost=0.0,
        )
        await store.create_run(run)
        return store

    return asyncio.run(_setup())


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def store_with_costs():
    return _make_stores_with_costs()


@pytest.fixture()
def store_no_costs():
    return _make_stores_no_costs()


# ── cost show ──────────────────────────────────────────────────────────


class TestCostShow:
    """Tests for `binex cost show <run_id>`."""

    def test_text_output_shows_total_and_breakdown(self, runner, store_with_costs):
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store_with_costs, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_show_cmd, ["run_test123"])

        assert result.exit_code == 0
        assert "$0.83" in result.output
        assert "planner" in result.output
        assert "$0.33" in result.output
        assert "researcher" in result.output
        assert "$0.50" in result.output
        assert "Node breakdown" in result.output

    def test_json_output_correct_structure(self, runner, store_with_costs):
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store_with_costs, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_show_cmd, ["run_test123", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["run_id"] == "run_test123"
        assert data["total_cost"] == pytest.approx(0.83)
        assert data["currency"] == "USD"
        assert "nodes" in data
        assert len(data["nodes"]) == 2

        node_ids = {n["task_id"] for n in data["nodes"]}
        assert node_ids == {"planner", "researcher"}

        planner = next(n for n in data["nodes"] if n["task_id"] == "planner")
        assert planner["cost"] == pytest.approx(0.33)
        assert planner["model"] == "gpt-4"
        assert planner["prompt_tokens"] == 100
        assert planner["completion_tokens"] == 50

    def test_run_not_found_returns_error(self, runner):
        store = asyncio.run(self._empty_store())
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_show_cmd, ["nonexistent_run"])

        assert result.exit_code != 0
        assert "not found" in result.output or "not found" in (result.stderr or "")

    def test_no_cost_records_shows_zero(self, runner, store_no_costs):
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store_no_costs, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_show_cmd, ["run_empty"])

        assert result.exit_code == 0
        assert "$0.00" in result.output

    @staticmethod
    async def _empty_store():
        return InMemoryExecutionStore()


# ── cost history ───────────────────────────────────────────────────────


class TestCostHistory:
    """Tests for `binex cost history <run_id>`."""

    def test_text_output_shows_events(self, runner, store_with_costs):
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store_with_costs, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_history_cmd, ["run_test123"])

        assert result.exit_code == 0
        assert "planner" in result.output
        assert "researcher" in result.output
        assert "$0.33" in result.output
        assert "$0.50" in result.output
        assert "llm_tokens" in result.output

    def test_json_output_correct_structure(self, runner, store_with_costs):
        with patch(
            "binex.cli.cost._get_stores",
            return_value=(store_with_costs, InMemoryArtifactStore()),
        ):
            result = runner.invoke(cost_history_cmd, ["run_test123", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["run_id"] == "run_test123"
        assert "records" in data
        assert len(data["records"]) == 2

        first = data["records"][0]
        assert "id" in first
        assert "task_id" in first
        assert "cost" in first
        assert "currency" in first
        assert "source" in first
        assert "timestamp" in first


# ── run command cost output ────────────────────────────────────────────


class TestRunCostOutput:
    """Tests for cost-related output in `binex run`."""

    @pytest.fixture()
    def workflow_file(self, tmp_path):
        """Create a dummy workflow file so click.Path(exists=True) passes."""
        f = tmp_path / "workflow.yaml"
        f.write_text("name: dummy\nnodes: {}\n")
        return str(f)

    def test_run_output_includes_cost_summary(self, runner, workflow_file):
        """Run output includes cost line when total_cost > 0."""
        from binex.cli.run import run_cmd

        summary = RunSummary(
            run_id="run_cost1",
            workflow_name="cost-wf",
            status="completed",
            total_nodes=1,
            completed_nodes=1,
            total_cost=1.25,
        )

        from unittest.mock import MagicMock
        spec = MagicMock()
        spec.nodes = {"step1": MagicMock(depends_on=[])}
        spec.budget = None

        with patch("binex.cli.run._get_stores") as mock_stores, \
             patch("binex.cli.run.load_workflow", return_value=spec), \
             patch("binex.cli.run.validate_workflow", return_value=[]), \
             patch("binex.cli.run._run", return_value=(summary, [], [])):

            mock_stores.return_value = (InMemoryExecutionStore(), InMemoryArtifactStore())
            result = runner.invoke(run_cmd, [workflow_file], catch_exceptions=False)

        assert "Cost: $1.25" in result.output

    def test_run_output_includes_budget_info(self, runner, workflow_file):
        """Run output includes budget line when budget is defined."""
        from binex.cli.run import run_cmd

        summary = RunSummary(
            run_id="run_budget1",
            workflow_name="budget-wf",
            status="completed",
            total_nodes=1,
            completed_nodes=1,
            total_cost=0.50,
        )

        from binex.models.cost import BudgetConfig
        from unittest.mock import MagicMock
        spec = MagicMock()
        spec.nodes = {"step1": MagicMock(depends_on=[])}
        spec.budget = BudgetConfig(max_cost=5.00, policy="warn")

        with patch("binex.cli.run._get_stores") as mock_stores, \
             patch("binex.cli.run.load_workflow", return_value=spec), \
             patch("binex.cli.run.validate_workflow", return_value=[]), \
             patch("binex.cli.run._run", return_value=(summary, [], [])):

            mock_stores.return_value = (InMemoryExecutionStore(), InMemoryArtifactStore())
            result = runner.invoke(run_cmd, [workflow_file], catch_exceptions=False)

        assert "Budget: $5.00" in result.output
        assert "remaining: $4.50" in result.output

    def test_run_output_shows_over_budget_status(self, runner, workflow_file):
        """Run output shows budget exceeded message when status is over_budget."""
        from binex.cli.run import run_cmd

        summary = RunSummary(
            run_id="run_over",
            workflow_name="over-wf",
            status="over_budget",
            total_nodes=3,
            completed_nodes=2,
            failed_nodes=0,
            total_cost=12.00,
        )

        from binex.models.cost import BudgetConfig
        from unittest.mock import MagicMock
        spec = MagicMock()
        spec.nodes = {
            "a": MagicMock(depends_on=[]),
            "b": MagicMock(depends_on=["a"]),
            "c": MagicMock(depends_on=["b"]),
        }
        spec.budget = BudgetConfig(max_cost=10.00, policy="stop")

        with patch("binex.cli.run._get_stores") as mock_stores, \
             patch("binex.cli.run.load_workflow", return_value=spec), \
             patch("binex.cli.run.validate_workflow", return_value=[]), \
             patch("binex.cli.run._run", return_value=(summary, [], [])):

            mock_stores.return_value = (InMemoryExecutionStore(), InMemoryArtifactStore())
            result = runner.invoke(run_cmd, [workflow_file])

        assert result.exit_code == 1
        assert "Budget exceeded" in result.output or "budget exceeded" in result.output.lower()
        assert "$12.00" in result.output
        assert "$10.00" in result.output
