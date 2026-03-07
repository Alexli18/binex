"""Tests for CLI `binex replay` and `binex diff` commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.execution import RunSummary


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_replay_command_exists(runner: CliRunner):
    """The replay command should be registered."""
    result = runner.invoke(cli, ["replay", "--help"])
    assert result.exit_code == 0
    assert "replay" in result.output.lower()


def test_diff_command_exists(runner: CliRunner):
    """The diff command should be registered."""
    result = runner.invoke(cli, ["diff", "--help"])
    assert result.exit_code == 0


def test_replay_requires_run_id(runner: CliRunner):
    """Replay without run-id should fail."""
    result = runner.invoke(cli, ["replay"])
    assert result.exit_code != 0


def test_replay_requires_from_flag(runner: CliRunner):
    """Replay without --from should show error."""
    result = runner.invoke(cli, ["replay", "run_123"])
    assert result.exit_code != 0


def test_diff_requires_two_run_ids(runner: CliRunner):
    """Diff without two run IDs should fail."""
    result = runner.invoke(cli, ["diff", "run_a"])
    assert result.exit_code != 0


def test_replay_invokes_engine(runner: CliRunner):
    """Replay should invoke ReplayEngine and display output."""
    mock_summary = RunSummary(
        run_id="run_new_123",
        workflow_name="test-pipeline",
        status="completed",
        total_nodes=3,
        completed_nodes=3,
        forked_from="run_original",
        forked_at_step="b",
    )

    with patch("binex.cli.replay._run_replay", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_summary
        result = runner.invoke(
            cli, ["replay", "run_original", "--from", "b", "--workflow", "examples/simple.yaml"]
        )

    assert result.exit_code == 0
    assert "run_new_123" in result.output


def test_replay_json_output(runner: CliRunner):
    """--json flag should produce JSON output."""
    mock_summary = RunSummary(
        run_id="run_new_123",
        workflow_name="test-pipeline",
        status="completed",
        total_nodes=3,
        completed_nodes=3,
        forked_from="run_original",
        forked_at_step="b",
    )

    with patch("binex.cli.replay._run_replay", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_summary
        result = runner.invoke(
            cli, ["replay", "run_original", "--from", "b", "--workflow", "examples/simple.yaml", "--json"]
        )

    assert result.exit_code == 0
    assert '"run_id"' in result.output


def test_diff_invokes_engine(runner: CliRunner):
    """Diff should invoke diff_runs and display output."""
    mock_diff = {
        "run_a": "run_1",
        "run_b": "run_2",
        "workflow_a": "test",
        "workflow_b": "test",
        "status_a": "completed",
        "status_b": "completed",
        "steps": [],
    }

    with patch("binex.cli.diff._run_diff", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_diff
        result = runner.invoke(cli, ["diff", "run_1", "run_2"])

    assert result.exit_code == 0
    assert "run_1" in result.output


def test_diff_json_output(runner: CliRunner):
    """--json flag should produce JSON output."""
    mock_diff = {
        "run_a": "run_1",
        "run_b": "run_2",
        "workflow_a": "test",
        "workflow_b": "test",
        "status_a": "completed",
        "status_b": "completed",
        "steps": [],
    }

    with patch("binex.cli.diff._run_diff", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = mock_diff
        result = runner.invoke(cli, ["diff", "run_1", "run_2", "--json"])

    assert result.exit_code == 0
    assert '"run_a"' in result.output
