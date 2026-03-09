"""Extended tests for CLI `binex replay` — covers uncovered paths in replay.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import click
import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.cli.replay import _parse_agent_swaps
from binex.models.execution import RunSummary


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# _parse_agent_swaps unit tests (lines 123-130)
# ---------------------------------------------------------------------------


class TestParseAgentSwaps:
    def test_valid_single_swap(self):
        result = _parse_agent_swaps(("nodeA=llm://gpt-4",))
        assert result == {"nodeA": "llm://gpt-4"}

    def test_valid_multiple_swaps(self):
        result = _parse_agent_swaps((
            "nodeA=llm://gpt-4",
            "nodeB=a2a://http://localhost:8000",
        ))
        assert result == {
            "nodeA": "llm://gpt-4",
            "nodeB": "a2a://http://localhost:8000",
        }

    def test_empty_tuple(self):
        result = _parse_agent_swaps(())
        assert result == {}

    def test_value_with_equals_sign(self):
        """An '=' in the agent value should be preserved (split on first '=' only)."""
        result = _parse_agent_swaps(("node=a2a://host?key=val",))
        assert result == {"node": "a2a://host?key=val"}

    def test_invalid_format_no_equals(self):
        with pytest.raises(click.BadParameter, match="Invalid agent swap format"):
            _parse_agent_swaps(("bad-format",))

    def test_invalid_format_mixed(self):
        """First valid, second invalid — should raise on the invalid one."""
        with pytest.raises(click.BadParameter, match="no-equals"):
            _parse_agent_swaps(("good=llm://x", "no-equals"))


# ---------------------------------------------------------------------------
# replay_cmd integration tests via CliRunner
# ---------------------------------------------------------------------------


def _make_summary(**overrides) -> RunSummary:
    defaults = dict(
        run_id="run_replay_001",
        workflow_name="test-pipeline",
        status="completed",
        total_nodes=4,
        completed_nodes=4,
        failed_nodes=0,
        forked_from="run_original",
        forked_at_step="step_b",
    )
    defaults.update(overrides)
    return RunSummary(**defaults)


class TestReplayCmdValueError:
    """replay_cmd when _run_replay raises ValueError (lines 30-32)."""

    def test_value_error_shows_message_and_exits_1(self, runner: CliRunner):
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            side_effect=ValueError("step 'xyz' not found in original run"),
        ):
            result = runner.invoke(
                cli,
                ["replay", "run_orig", "--from", "xyz", "--workflow", "examples/simple.yaml"],
            )

        assert result.exit_code == 1
        assert "Error: step 'xyz' not found in original run" in result.output


class TestReplayCmdFailedStatus:
    """replay_cmd when status is not 'completed' (exit code 1, failed line)."""

    def test_failed_status_exits_1(self, runner: CliRunner):
        summary = _make_summary(status="failed", completed_nodes=2, failed_nodes=2)
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            return_value=summary,
        ):
            result = runner.invoke(
                cli,
                ["replay", "run_orig", "--from", "step_b", "--workflow", "examples/simple.yaml"],
            )

        assert result.exit_code == 1
        assert "Status: failed" in result.output
        assert "Nodes: 2/4 completed" in result.output
        assert "Failed: 2" in result.output

    def test_completed_status_exits_0(self, runner: CliRunner):
        summary = _make_summary(status="completed")
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            return_value=summary,
        ):
            result = runner.invoke(
                cli,
                ["replay", "run_orig", "--from", "step_b", "--workflow", "examples/simple.yaml"],
            )

        assert result.exit_code == 0
        assert "Status: completed" in result.output

    def test_no_failed_line_when_zero_failures(self, runner: CliRunner):
        summary = _make_summary(status="completed", failed_nodes=0)
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            return_value=summary,
        ):
            result = runner.invoke(
                cli,
                ["replay", "run_orig", "--from", "step_b", "--workflow", "examples/simple.yaml"],
            )

        assert result.exit_code == 0
        assert "Failed:" not in result.output


class TestReplayCmdOutputFormat:
    """Verify the text output lines (lines 37-43)."""

    def test_text_output_includes_all_fields(self, runner: CliRunner):
        summary = _make_summary(
            run_id="run_replay_999",
            workflow_name="my-workflow",
            status="completed",
            total_nodes=5,
            completed_nodes=5,
            forked_from="run_orig_abc",
            forked_at_step="step_x",
        )
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            return_value=summary,
        ):
            result = runner.invoke(
                cli,
                ["replay", "run_orig_abc", "--from", "step_x", "--workflow", "examples/simple.yaml"],
            )

        assert "Replay Run ID: run_replay_999" in result.output
        assert "Forked from: run_orig_abc at step 'step_x'" in result.output
        assert "Workflow: my-workflow" in result.output
        assert "Status: completed" in result.output
        assert "Nodes: 5/5 completed" in result.output

    def test_json_output_with_failed_status(self, runner: CliRunner):
        summary = _make_summary(status="failed", failed_nodes=1, completed_nodes=3)
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            return_value=summary,
        ):
            result = runner.invoke(
                cli,
                [
                    "replay", "run_orig", "--from", "step_b",
                    "--workflow", "examples/simple.yaml", "--json",
                ],
            )

        assert '"status": "failed"' in result.output
        assert '"failed_nodes": 1' in result.output
        assert result.exit_code == 1


class TestReplayCmdAgentSwapViaCLI:
    """Ensure --agent flags are parsed and forwarded correctly."""

    def test_agent_swap_invalid_via_cli(self, runner: CliRunner):
        """Invalid --agent value should cause BadParameter before _run_replay."""
        result = runner.invoke(
            cli,
            [
                "replay", "run_orig", "--from", "step_b",
                "--workflow", "examples/simple.yaml",
                "--agent", "no-equals-here",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid agent swap format" in result.output

    def test_agent_swap_valid_forwarded(self, runner: CliRunner):
        summary = _make_summary()
        with patch(
            "binex.cli.replay._run_replay",
            new_callable=AsyncMock,
            return_value=summary,
        ) as mock_run:
            result = runner.invoke(
                cli,
                [
                    "replay", "run_orig", "--from", "step_b",
                    "--workflow", "examples/simple.yaml",
                    "--agent", "nodeA=llm://gpt-4",
                    "--agent", "nodeB=a2a://localhost:9000",
                ],
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        agent_swaps = call_args[0][3] if call_args[0] else call_args.kwargs.get("agent_swaps")
        assert agent_swaps == {"nodeA": "llm://gpt-4", "nodeB": "a2a://localhost:9000"}
