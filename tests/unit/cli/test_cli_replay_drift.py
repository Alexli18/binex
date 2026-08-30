"""`binex replay` must surface workflow drift instead of replaying stale cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.execution import RunSummary
from binex.runtime.replay import WorkflowDriftError


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_drift_error_exits_2_with_message(runner: CliRunner):
    """A drifted cached node aborts the replay with the dedicated exit code."""
    with patch("binex.cli.replay._run_replay", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = WorkflowDriftError(["a"], "run_original")
        result = runner.invoke(cli, [
            "replay", "run_original", "--from", "b",
            "--workflow", "examples/simple.yaml",
        ])

    assert result.exit_code == 2
    assert "'a'" in result.output
    assert "--allow-drift" in result.output


def test_allow_drift_flag_is_forwarded(runner: CliRunner):
    """--allow-drift reaches the engine so the stale cache is reused knowingly."""
    summary = RunSummary(
        run_id="run_new", workflow_name="test-pipeline", status="completed",
        total_nodes=3, completed_nodes=3,
        forked_from="run_original", forked_at_step="b",
    )

    with patch("binex.cli.replay._run_replay", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = summary
        result = runner.invoke(cli, [
            "replay", "run_original", "--from", "b",
            "--workflow", "examples/simple.yaml", "--allow-drift",
        ])

    assert result.exit_code == 0
    assert mock_run.call_args.kwargs.get("allow_drift") is True


def test_allow_drift_defaults_to_false(runner: CliRunner):
    """Without the flag the gate stays armed."""
    summary = RunSummary(
        run_id="run_new", workflow_name="test-pipeline", status="completed",
        total_nodes=3, completed_nodes=3,
    )

    with patch("binex.cli.replay._run_replay", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = summary
        runner.invoke(cli, [
            "replay", "run_original", "--from", "b",
            "--workflow", "examples/simple.yaml",
        ])

    assert mock_run.call_args.kwargs.get("allow_drift") is False
