"""Extended tests for cli/dev.py and cli/diff.py — covering previously uncovered lines."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import click
import httpx
import pytest
from click.testing import CliRunner

from binex.cli.dev import _run_compose, _wait_for_health, dev_cmd
from binex.cli.main import cli


# ---------------------------------------------------------------------------
# dev.py — _run_compose
# ---------------------------------------------------------------------------


@patch("binex.cli.dev.subprocess.run")
def test_run_compose_calls_subprocess(mock_run):
    """_run_compose builds the correct command and delegates to subprocess.run."""
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
    compose_file = Path("/fake/docker-compose.yml")

    result = _run_compose(compose_file, "up", "-d")

    mock_run.assert_called_once_with(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# dev.py — _wait_for_health
# ---------------------------------------------------------------------------


@patch("binex.cli.dev.time.sleep")
@patch("binex.cli.dev.httpx.get")
@patch("binex.cli.dev.time.time")
def test_wait_for_health_returns_true_on_200(mock_time, mock_get, mock_sleep):
    """Immediate 200 response means the function returns True right away."""
    mock_time.side_effect = [0, 0]
    mock_resp = MagicMock(status_code=200)
    mock_get.return_value = mock_resp

    result = _wait_for_health("http://localhost:1234/health", "TestService", timeout=10)

    assert result is True
    mock_get.assert_called_once_with("http://localhost:1234/health", timeout=5.0)


@patch("binex.cli.dev.time.sleep")
@patch("binex.cli.dev.httpx.get")
@patch("binex.cli.dev.time.time")
def test_wait_for_health_retries_on_connect_error(mock_time, mock_get, mock_sleep):
    """ConnectError on first attempt, then 200 on second — should return True."""
    mock_time.side_effect = [0, 0, 0]
    mock_get.side_effect = [
        httpx.ConnectError("refused"),
        MagicMock(status_code=200),
    ]

    result = _wait_for_health("http://localhost:1234/health", "TestService", timeout=100)

    assert result is True
    assert mock_get.call_count == 2
    mock_sleep.assert_called_once_with(2)


@patch("binex.cli.dev.time.sleep")
@patch("binex.cli.dev.httpx.get")
@patch("binex.cli.dev.time.time")
def test_wait_for_health_returns_false_on_timeout(mock_time, mock_get, mock_sleep):
    """All attempts raise ConnectError and timeout expires — returns False."""
    mock_time.side_effect = [0, 1]
    mock_get.side_effect = httpx.ConnectError("refused")

    result = _wait_for_health("http://localhost:1234/health", "TestService", timeout=0.01)

    assert result is False


# ---------------------------------------------------------------------------
# dev.py — dev_cmd foreground mode (no --detach)
# ---------------------------------------------------------------------------


@patch("binex.cli.dev.subprocess.run")
@patch("binex.cli.dev._find_compose_file")
def test_dev_cmd_foreground_calls_subprocess(mock_find, mock_run):
    """Foreground mode (no --detach) should call subprocess.run directly."""
    compose_path = Path("/fake/docker-compose.yml")
    mock_find.return_value = compose_path
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

    runner = CliRunner()
    result = runner.invoke(dev_cmd, [])

    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        [
            "docker", "compose", "-f", str(compose_path),
            "up", "--build", "--remove-orphans",
        ],
        check=False,
    )


# ---------------------------------------------------------------------------
# dev.py — compose file not found path
# ---------------------------------------------------------------------------


@patch("binex.cli.dev._find_compose_file", side_effect=click.ClickException("not found"))
def test_dev_cmd_compose_not_found(mock_find):
    """When _find_compose_file raises ClickException, exit code 2 and error message."""
    runner = CliRunner()
    result = runner.invoke(dev_cmd, [])

    assert result.exit_code == 2
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# diff.py — ValueError path
# ---------------------------------------------------------------------------


@patch("binex.cli.diff._run_diff", side_effect=ValueError("run xyz not found"))
def test_diff_cmd_value_error(mock_run_diff):
    """ValueError from _run_diff should print error message and exit 1."""
    runner = CliRunner()
    result = runner.invoke(cli, ["diff", "run-a", "run-b"])

    assert result.exit_code == 1
    assert "run xyz not found" in result.output


# ---------------------------------------------------------------------------
# diff.py — _run_diff integration (stores.close called)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_diff_calls_close():
    """_run_diff should call exec_store.close() even on success."""
    from binex.cli.diff import _run_diff

    mock_exec = AsyncMock()
    mock_art = MagicMock()
    mock_diff_result = {"status": "identical"}

    with (
        patch("binex.cli.diff.get_stores", return_value=(mock_exec, mock_art)),
        patch("binex.trace.diff.diff_runs", new_callable=AsyncMock, return_value=mock_diff_result) as mock_diff_runs,
    ):
        result = await _run_diff("run-a", "run-b")

    assert result == mock_diff_result
    mock_diff_runs.assert_awaited_once_with(mock_exec, mock_art, "run-a", "run-b")
    mock_exec.close.assert_awaited_once()
