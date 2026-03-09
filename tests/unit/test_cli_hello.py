"""Tests for binex hello CLI command."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from binex.cli.hello import hello_cmd
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_stores():
    return InMemoryExecutionStore(), InMemoryArtifactStore()


def test_hello_cmd_success():
    """CliRunner invokes hello, verify exit code 0."""
    stores = _make_stores()
    with patch("binex.cli.hello._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(hello_cmd, [])

    assert result.exit_code == 0, result.output


def test_hello_cmd_shows_run_id():
    """Verify 'Run ID:' appears in output."""
    stores = _make_stores()
    with patch("binex.cli.hello._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(hello_cmd, [])

    assert "Run ID:" in result.output


def test_hello_cmd_shows_next_steps():
    """Verify 'Next steps:' appears in output."""
    stores = _make_stores()
    with patch("binex.cli.hello._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(hello_cmd, [])

    assert "Next steps:" in result.output


def test_hello_cmd_shows_node_progress():
    """Verify '[1/2]' and '[2/2]' appear in output."""
    stores = _make_stores()
    with patch("binex.cli.hello._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(hello_cmd, [])

    assert "[1/2]" in result.output
    assert "[2/2]" in result.output
