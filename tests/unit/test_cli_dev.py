"""Tests for binex dev CLI command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from binex.cli.dev import dev_cmd, _find_compose_file


class TestFindComposeFile:
    def test_finds_compose_in_cwd(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker" / "docker-compose.yml"
        compose.parent.mkdir(parents=True)
        compose.write_text("version: '3'")
        with patch("binex.cli.dev.Path.cwd", return_value=tmp_path):
            result = _find_compose_file()
            assert result == compose

    def test_raises_when_not_found(self, tmp_path: Path) -> None:
        import click
        import pytest
        with patch("binex.cli.dev.Path.cwd", return_value=tmp_path):
            with patch("binex.cli.dev.__file__", str(tmp_path / "cli" / "dev.py")):
                with pytest.raises(click.ClickException):
                    _find_compose_file()


class TestDevCommand:
    def test_dev_no_compose_file(self) -> None:
        runner = CliRunner()
        with patch("binex.cli.dev._find_compose_file", side_effect=Exception("not found")):
            result = runner.invoke(dev_cmd)
            assert result.exit_code != 0

    def test_dev_detach_starts_compose(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with (
            patch("binex.cli.dev._find_compose_file", return_value=compose_file),
            patch("binex.cli.dev._run_compose", return_value=mock_result),
            patch("binex.cli.dev._wait_for_health", return_value=True),
        ):
            runner = CliRunner()
            result = runner.invoke(dev_cmd, ["--detach"])
            assert result.exit_code == 0
            assert "Starting Binex" in result.output

    def test_dev_detach_reports_unhealthy(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with (
            patch("binex.cli.dev._find_compose_file", return_value=compose_file),
            patch("binex.cli.dev._run_compose", return_value=mock_result),
            patch("binex.cli.dev._wait_for_health", return_value=False),
        ):
            runner = CliRunner()
            result = runner.invoke(dev_cmd, ["--detach"])
            assert "Some services failed" in result.output

    def test_dev_compose_failure(self, tmp_path: Path) -> None:
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: something went wrong"

        with (
            patch("binex.cli.dev._find_compose_file", return_value=compose_file),
            patch("binex.cli.dev._run_compose", return_value=mock_result),
        ):
            runner = CliRunner()
            result = runner.invoke(dev_cmd, ["--detach"])
            assert result.exit_code != 0
