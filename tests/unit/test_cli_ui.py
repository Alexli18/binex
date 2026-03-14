"""Tests for the `binex ui` CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from binex.cli.main import cli


def test_ui_command_registered():
    runner = CliRunner()
    result = runner.invoke(cli, ["ui", "--help"])
    assert result.exit_code == 0
    assert "Launch the Binex web UI" in result.output


def test_ui_command_default_options():
    runner = CliRunner()
    result = runner.invoke(cli, ["ui", "--help"])
    assert "--port" in result.output
    assert "--host" in result.output
    assert "--dev" in result.output
    assert "--no-browser" in result.output


@patch("binex.cli.ui_cmd.uvicorn")
@patch("binex.cli.ui_cmd.webbrowser")
def test_ui_command_runs_server(mock_browser, mock_uvicorn):
    runner = CliRunner()
    result = runner.invoke(cli, ["ui", "--no-browser", "--port", "9999"])
    assert result.exit_code == 0
    mock_uvicorn.run.assert_called_once()
    call_kwargs = mock_uvicorn.run.call_args
    assert call_kwargs.kwargs["port"] == 9999
    assert call_kwargs.kwargs["host"] == "127.0.0.1"
    mock_browser.open.assert_not_called()


@patch("binex.cli.ui_cmd.uvicorn")
@patch("binex.cli.ui_cmd.webbrowser")
def test_ui_command_opens_browser_by_default(mock_browser, mock_uvicorn):
    runner = CliRunner()
    result = runner.invoke(cli, ["ui"])
    assert result.exit_code == 0
    mock_browser.open.assert_called_once_with("http://127.0.0.1:8420")
