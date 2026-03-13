"""Tests for `binex plugins list` and `binex plugins check` CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from binex.cli.main import cli


def _make_entry_point(name: str, value: str, *, pkg: str = "binex-fake", version: str = "1.0.0"):
    ep = MagicMock()
    ep.name = name
    ep.value = value
    ep.dist = MagicMock()
    ep.dist.name = pkg
    ep.dist.version = version
    ep.load.return_value = type("FakePlugin", (), {"prefix": name, "create_adapter": lambda s, u, c: None})
    return ep


# ---------------------------------------------------------------------------
# T017: plugins list tests
# ---------------------------------------------------------------------------

class TestPluginsList:
    def test_shows_builtins_and_installed_plugins(self):
        ep = _make_entry_point("langchain", "binex_langchain:LC", pkg="binex-langchain", version="0.1.0")
        runner = CliRunner()
        with patch("binex.cli.plugins_cmd.PluginRegistry.discover") as mock_discover, \
             patch("binex.cli.plugins_cmd.PluginRegistry.all_plugins") as mock_all:
            mock_discover.return_value = []
            mock_all.return_value = [
                {"prefix": "langchain", "name": "langchain", "package_name": "binex-langchain", "version": "0.1.0"},
            ]
            result = runner.invoke(cli, ["plugins", "list"])

        assert result.exit_code == 0
        assert "Built-in adapters:" in result.output
        assert "local://" in result.output
        assert "llm://" in result.output
        assert "Installed plugins:" in result.output
        assert "langchain://" in result.output
        assert "binex-langchain" in result.output
        assert "0.1.0" in result.output

    def test_shows_no_plugins_message_when_empty(self):
        runner = CliRunner()
        with patch("binex.cli.plugins_cmd.PluginRegistry.discover"), \
             patch("binex.cli.plugins_cmd.PluginRegistry.all_plugins", return_value=[]):
            result = runner.invoke(cli, ["plugins", "list"])

        assert result.exit_code == 0
        assert "No plugins installed." in result.output

    def test_json_output_matches_contract(self):
        runner = CliRunner()
        with patch("binex.cli.plugins_cmd.PluginRegistry.discover"), \
             patch("binex.cli.plugins_cmd.PluginRegistry.all_plugins") as mock_all:
            mock_all.return_value = [
                {"prefix": "langchain", "name": "langchain", "package_name": "binex-langchain", "version": "0.1.0"},
            ]
            result = runner.invoke(cli, ["plugins", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "builtins" in data
        assert "plugins" in data
        assert len(data["builtins"]) == 4
        assert data["builtins"][0]["prefix"] == "local"
        assert data["plugins"][0]["prefix"] == "langchain"
        assert data["plugins"][0]["package"] == "binex-langchain"
        assert data["plugins"][0]["version"] == "0.1.0"


# ---------------------------------------------------------------------------
# T019: plugins check tests
# ---------------------------------------------------------------------------

class TestPluginsCheck:
    def test_valid_workflow_exits_0(self, tmp_path):
        wf = tmp_path / "workflow.yaml"
        wf.write_text("name: test\nnodes:\n  a:\n    agent: 'local://handler'\n    outputs: [r]\n")

        runner = CliRunner()
        with patch("binex.cli.plugins_cmd.PluginRegistry.discover"), \
             patch("binex.cli.plugins_cmd.PluginRegistry.all_plugins", return_value=[]):
            result = runner.invoke(cli, ["plugins", "check", str(wf)])

        assert result.exit_code == 0
        assert "\u2713" in result.output
        assert "built-in" in result.output

    def test_missing_plugin_exits_1(self, tmp_path):
        wf = tmp_path / "workflow.yaml"
        wf.write_text("name: test\nnodes:\n  a:\n    agent: 'nonexistent://x'\n    outputs: [r]\n")

        runner = CliRunner()
        with patch("binex.cli.plugins_cmd.PluginRegistry.discover"), \
             patch("binex.cli.plugins_cmd.PluginRegistry.all_plugins", return_value=[]):
            result = runner.invoke(cli, ["plugins", "check", str(wf)])

        assert result.exit_code == 1
        assert "\u2717" in result.output
        assert "not found" in result.output
        assert "1 missing adapter(s)" in result.output

    def test_mixed_builtins_and_plugins_show_correct_sources(self, tmp_path):
        wf = tmp_path / "workflow.yaml"
        wf.write_text(
            "name: test\nnodes:\n"
            "  a:\n    agent: 'local://handler'\n    outputs: [r]\n"
            "  b:\n    agent: 'langchain://chain'\n    outputs: [r]\n"
        )

        runner = CliRunner()
        with patch("binex.cli.plugins_cmd.PluginRegistry.discover"), \
             patch("binex.cli.plugins_cmd.PluginRegistry.all_plugins") as mock_all:
            mock_all.return_value = [
                {"prefix": "langchain", "name": "langchain", "package_name": "binex-langchain", "version": "0.1.0"},
            ]
            result = runner.invoke(cli, ["plugins", "check", str(wf)])

        assert result.exit_code == 0
        assert "built-in" in result.output
        assert "plugin" in result.output
        assert "binex-langchain" in result.output
