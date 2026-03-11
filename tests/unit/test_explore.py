"""Tests for `binex explore` interactive dashboard."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

PATCH_TARGET = "binex.cli.explore._get_stores"


def _make_stores(runs=None, artifacts=None, records=None, costs=None):
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    async def setup():
        for r in (runs or []):
            await exec_store.create_run(r)
        for a in (artifacts or []):
            await art_store.store(a)
        for rec in (records or []):
            await exec_store.record(rec)
        for c in (costs or []):
            await exec_store.record_cost(c)

    asyncio.run(setup())
    return exec_store, art_store


def _run(
    run_id="run_abc123",
    name="test-workflow",
    status="completed",
    total_nodes=2,
    completed_nodes=2,
    total_cost=0.0,
):
    return RunSummary(
        run_id=run_id,
        workflow_name=name,
        status=status,
        started_at=datetime.now(UTC),
        total_nodes=total_nodes,
        completed_nodes=completed_nodes,
        total_cost=total_cost,
    )


def _record(
    rec_id="rec_1",
    run_id="run_abc123",
    task_id="step1",
    agent_id="llm://gpt-4o",
    status=TaskStatus.COMPLETED,
    latency_ms=100,
):
    return ExecutionRecord(
        id=rec_id,
        run_id=run_id,
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        latency_ms=latency_ms,
        trace_id="trace_1",
    )


def _artifact(
    art_id="art_1",
    run_id="run_abc123",
    node="step1",
    atype="text",
    content="hello",
):
    return Artifact(
        id=art_id,
        run_id=run_id,
        type=atype,
        content=content,
        status="complete",
        lineage=Lineage(produced_by=node),
    )


def _cost(
    cost_id="cost_1",
    run_id="run_abc123",
    task_id="step1",
    cost=0.01,
):
    return CostRecord(
        id=cost_id,
        run_id=run_id,
        task_id=task_id,
        cost=cost,
        source="llm_tokens",
    )


class TestExploreNoRuns:
    def test_no_runs_shows_help(self):
        stores = _make_stores()
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "No runs found" in result.output

    def test_no_runs_suggests_command(self):
        stores = _make_stores()
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "binex run" in result.output


class TestExploreRunSelection:
    def test_lists_runs_and_quit(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "test-workflow" in result.output
        assert "run_abc123" in result.output

    def test_select_run_shows_dashboard(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="1\nq\n")
        assert "Dashboard" in result.output or "dashboard" in result.output.lower()

    def test_invalid_choice_reprompts(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="99\nq\n")
        assert "Invalid choice" in result.output

    def test_multiple_runs_listed(self):
        r1 = _run("run_old", "old-wf")
        r2 = _run("run_new", "new-wf")
        stores = _make_stores(runs=[r1, r2])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "old-wf" in result.output
        assert "new-wf" in result.output


class TestExploreDirectRunId:
    def test_jump_to_dashboard(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "test-workflow" in result.output
        assert result.exit_code == 0

    def test_run_not_found(self):
        stores = _make_stores()
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "nonexistent"])
        assert "not found" in result.output


class TestDashboardDisplay:
    def test_shows_run_info(self):
        stores = _make_stores(
            runs=[_run(total_cost=0.05)],
            records=[
                _record(task_id="step1", agent_id="llm://gpt-4o"),
                _record(
                    rec_id="rec_2", task_id="step2",
                    agent_id="local://echo", latency_ms=50,
                ),
            ],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "test-workflow" in result.output
        assert "step1" in result.output
        assert "step2" in result.output

    def test_shows_status(self):
        stores = _make_stores(
            runs=[_run(status="completed")],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "completed" in result.output

    def test_no_records_shown(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        # Dashboard renders with an empty node table (rich) or "(no execution records)" (plain)
        assert result.exit_code == 0
        assert "run_abc123" in result.output


class TestActionTrace:
    def test_trace_action(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="t\n\nq\n")
        # Should show trace output then return to dashboard
        assert result.exit_code == 0


class TestActionGraph:
    def test_graph_action(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="g\n\nq\n")
        assert result.exit_code == 0

    def test_graph_no_records(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="g\n\nq\n")
        assert "No records" in result.output


class TestActionDebug:
    def test_debug_action(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
            artifacts=[_artifact()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="d\n\nq\n")
        assert result.exit_code == 0
        # Debug report should show workflow name or node info
        assert "test-workflow" in result.output or "step1" in result.output


class TestActionCost:
    def test_cost_action(self):
        stores = _make_stores(
            runs=[_run(total_cost=0.01)],
            records=[_record()],
            costs=[_cost()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="c\n\nq\n")
        assert result.exit_code == 0

    def test_cost_no_costs(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="c\n\nq\n")
        assert result.exit_code == 0


class TestActionArtifacts:
    def test_artifacts_action_and_back(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
            artifacts=[_artifact(content="Hello World!")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="a\nb\n\nq\n",
            )
        assert "step1" in result.output
        assert result.exit_code == 0

    def test_artifacts_select_and_back(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
            artifacts=[_artifact(content="Hello World!")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="a\n1\nb\nb\n\nq\n",
            )
        assert "Hello World!" in result.output

    def test_no_artifacts(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="a\n\nq\n",
            )
        assert "No artifacts" in result.output


class TestActionNode:
    def test_node_action_list(self):
        stores = _make_stores(
            runs=[_run()],
            records=[
                _record(task_id="step1"),
                _record(rec_id="rec_2", task_id="step2"),
            ],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="n\nb\n\nq\n",
            )
        assert "step1" in result.output
        assert "step2" in result.output

    def test_node_select_detail(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1", agent_id="llm://gpt-4o")],
            artifacts=[_artifact(node="step1", content="output data")],
            costs=[_cost(task_id="step1", cost=0.005)],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="n\n1\n\nq\n",
            )
        assert "step1" in result.output
        assert "llm://gpt-4o" in result.output

    def test_node_no_records(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="n\n\nq\n",
            )
        assert "No execution records" in result.output


class TestActionReplay:
    def test_replay_blocked_when_running(self):
        stores = _make_stores(
            runs=[_run(status="running")],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="r\n\nq\n",
            )
        assert "Cannot replay a running workflow" in result.output

    def test_replay_cancel(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="r\nc\n\nq\n",
            )
        assert "cancelled" in result.output.lower()

    def test_replay_no_records(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="r\n\nq\n",
            )
        assert "No execution records" in result.output

    def test_replay_wizard_decline(self):
        """User selects node, skips swaps, enters workflow, then declines."""
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="r\n1\ndone\nworkflow.yaml\nn\n\nq\n",
            )
        assert "cancelled" in result.output.lower()


class TestDashboardMenuLoop:
    def test_unknown_action(self):
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="x\nq\n",
            )
        assert "Unknown action" in result.output

    def test_quit_from_wait(self):
        """User performs an action then quits from the wait prompt."""
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"], input="t\nq\n",
            )
        assert result.exit_code == 0


class TestEdgeCases:
    def test_short_id(self):
        from binex.cli.explore import _short_id
        assert _short_id("abcdefgh") == "abcdefgh"
        assert len(_short_id("a" * 32)) == 16

    def test_preview_none(self):
        from binex.cli.explore import _preview
        assert _preview(None) == "(empty)"

    def test_preview_truncates(self):
        from binex.cli.explore import _preview
        long = "x" * 100
        result = _preview(long, max_len=10)
        assert result.endswith("...")
        assert len(result) == 13  # 10 + "..."

    def test_preview_dict(self):
        from binex.cli.explore import _preview
        result = _preview({"key": "value"})
        assert "key" in result

    def test_time_ago(self):
        from binex.cli.explore import _time_ago
        result = _time_ago(datetime.now(UTC))
        assert "ago" in result


class TestReplayWizardAgentSwaps:
    """Test the agent swap loop in the replay wizard."""

    def test_swap_one_agent_then_decline(self):
        """Select node, enter agent swap, done, enter workflow, decline."""
        stores = _make_stores(
            runs=[_run()],
            records=[
                _record(task_id="step1", agent_id="llm://gpt-4o"),
            ],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="r\n1\nstep1=llm://new-model\ndone\nworkflow.yaml\nn\n\nq\n",
            )
        assert "step1" in result.output
        assert "Replay cancelled" in result.output
        assert result.exit_code == 0

    def test_swap_bad_format_then_done(self):
        """Enter bad swap format, get help message, then done."""
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="r\n1\nbadformat\ndone\nworkflow.yaml\nn\n\nq\n",
            )
        assert "Format: node=agent" in result.output
        assert result.exit_code == 0

    def test_swap_invalid_node_selection(self):
        """Select invalid node number in replay wizard."""
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="r\n99\n\nq\n",
            )
        assert "Invalid node selection" in result.output

    def test_swap_non_numeric_node_selection(self):
        """Enter non-numeric value for node selection."""
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="r\nabc\n\nq\n",
            )
        assert "Invalid node selection" in result.output

    def test_swap_shows_confirm_summary(self):
        """After swap and workflow entry, shows replay summary before confirm."""
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="r\n1\nstep1=llm://claude\ndone\nmy_workflow.yaml\nn\n\nq\n",
            )
        assert "step1" in result.output
        assert "my_workflow.yaml" in result.output


class TestEdgeCasesAdditional:
    """Additional edge case tests."""

    def test_multiple_runs_sorted_newest_first(self):
        """Runs should be listed with newest first."""
        from datetime import timedelta

        old = _run("run_old", "old-wf")
        old.started_at = datetime.now(UTC) - timedelta(hours=2)
        new = _run("run_new", "new-wf")
        new.started_at = datetime.now(UTC)
        stores = _make_stores(runs=[old, new])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        # Both runs should appear
        assert "old-wf" in result.output
        assert "new-wf" in result.output
        # Newest first: new-wf should appear before old-wf
        pos_new = result.output.index("new-wf")
        pos_old = result.output.index("old-wf")
        assert pos_new < pos_old

    def test_artifact_detail_lineage_action(self):
        """Selecting lineage on an artifact shows lineage info."""
        art = _artifact(content="data output")
        stores = _make_stores(
            runs=[_run()],
            records=[_record()],
            artifacts=[art],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="a\n1\nl\nb\n\nq\n",
            )
        # Should show artifact detail then lineage (or no lineage message)
        assert "data output" in result.output or "lineage" in result.output.lower()
        assert result.exit_code == 0

    def test_node_inspect_shows_artifact_content(self):
        """Node inspect displays artifacts produced by that node."""
        art = _artifact(node="step1", content="node output result")
        stores = _make_stores(
            runs=[_run()],
            records=[_record(task_id="step1", agent_id="llm://gpt-4o")],
            artifacts=[art],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="n\n1\n\nq\n",
            )
        assert "node output result" in result.output
        assert "Artifacts" in result.output

    def test_cost_action_no_cost_shows_zero(self):
        """Cost action with no cost data should still render without error."""
        stores = _make_stores(
            runs=[_run(total_cost=0.0)],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(
                cli, ["explore", "run_abc123"],
                input="c\n\nq\n",
            )
        # Should show $0.00 total or "no billed nodes" message
        assert "$0.00" in result.output or "no billed nodes" in result.output
        assert result.exit_code == 0


class TestDashboardDisplayExtended:
    """Extended dashboard display tests."""

    def test_dashboard_shows_workflow_name(self):
        """Dashboard should display the workflow name."""
        stores = _make_stores(
            runs=[_run(name="my-cool-workflow")],
            records=[_record()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "my-cool-workflow" in result.output

    def test_dashboard_shows_node_agent_info(self):
        """Dashboard should display agent info for each node."""
        stores = _make_stores(
            runs=[_run()],
            records=[
                _record(task_id="step1", agent_id="llm://gpt-4o"),
                _record(
                    rec_id="rec_2", task_id="step2",
                    agent_id="local://echo",
                ),
            ],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "llm://gpt-4o" in result.output
        assert "local://echo" in result.output

    def test_dashboard_shows_cost_when_present(self):
        """Dashboard should show cost info when total_cost > 0."""
        stores = _make_stores(
            runs=[_run(total_cost=0.1234)],
            records=[_record()],
            costs=[_cost(cost=0.1234)],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "0.1234" in result.output
