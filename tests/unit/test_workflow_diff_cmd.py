"""Tests for binex workflow diff command."""

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from binex.cli.workflow_cmd import workflow_group


def test_workflow_diff_shows_differences():
    """binex workflow diff <run1> <run2> should show YAML diff."""
    snapshot1 = {"content": "name: v1\nnodes: {}\n", "version": 1}
    snapshot2 = {"content": "name: v2\nnodes: {}\n", "version": 1}

    mock_run1 = MagicMock(workflow_hash="hash1")
    mock_run2 = MagicMock(workflow_hash="hash2")

    mock_store = AsyncMock()
    mock_store.get_run = AsyncMock(side_effect=[mock_run1, mock_run2])
    mock_store.get_workflow_snapshot = AsyncMock(side_effect=[snapshot1, snapshot2])
    mock_store.close = AsyncMock()

    with patch("binex.cli.workflow_cmd._get_stores", return_value=(mock_store, None)):
        runner = CliRunner()
        result = runner.invoke(workflow_group, ["diff", "run_1", "run_2"])

    assert result.exit_code == 0
    assert "v1" in result.output or "v2" in result.output


def test_workflow_diff_identical():
    """Same hash should report no differences."""
    mock_run = MagicMock(workflow_hash="same_hash")

    mock_store = AsyncMock()
    mock_store.get_run = AsyncMock(return_value=mock_run)
    mock_store.close = AsyncMock()

    with patch("binex.cli.workflow_cmd._get_stores", return_value=(mock_store, None)):
        runner = CliRunner()
        result = runner.invoke(workflow_group, ["diff", "run_1", "run_2"])

    assert result.exit_code == 0
    assert "identical" in result.output.lower() or "no diff" in result.output.lower()
