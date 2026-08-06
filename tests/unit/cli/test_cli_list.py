"""Tests for `binex list` command."""

from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from binex.cli.main import cli


def test_list_finds_examples() -> None:
    """binex list should find bundled example workflows."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["examples"]) > 0
    for wf in data["examples"]:
        assert "name" in wf
        assert "path" in wf
        assert "nodes" in wf
        assert wf["nodes"] > 0


def test_list_finds_local_workflows(tmp_path: Path) -> None:
    """binex list should find .yaml workflows in current directory."""
    wf_content = 'name: test-wf\nnodes:\n  a:\n    agent: "local://echo"\n    outputs: [x]\n'
    (tmp_path / "my-workflow.yaml").write_text(wf_content)

    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["list", "--json"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["local"]) >= 1
    names = [w["name"] for w in data["local"]]
    assert "test-wf" in names


def test_list_ignores_non_workflow_yaml(tmp_path: Path) -> None:
    """YAML files without 'nodes' key should be ignored."""
    (tmp_path / "config.yaml").write_text("key: value\n")

    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["list", "--json"])
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data["local"]) == 0


def test_list_plain_output() -> None:
    """binex list without --json should produce readable text."""
    runner = CliRunner()
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output.lower()
