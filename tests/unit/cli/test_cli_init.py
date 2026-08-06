"""Tests for `binex init` (deprecated alias) and `binex start --quick`."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from binex.cli.main import cli


def test_init_shows_deprecation_warning() -> None:
    """binex init prints a deprecation warning."""
    runner = CliRunner()
    with patch("binex.cli.start._quick_start"):
        result = runner.invoke(cli, ["init"])
    assert "deprecated" in result.output.lower()
    assert "binex start" in result.output


def test_init_invokes_quick_start_and_creates_files(tmp_path: Path) -> None:
    """binex init delegates to start --quick and creates a working project."""
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # provider 1 (ollama), default model
        result = runner.invoke(cli, ["init"], input="\n1\n\n")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    assert "deprecated" in result.output.lower()
    # Quick start should have created files in cwd
    assert (tmp_path / "workflow.yaml").exists()
    wf = (tmp_path / "workflow.yaml").read_text()
    assert "planner" in wf


def test_init_hidden_from_help() -> None:
    """binex init should not appear in --help output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # init should be hidden
    lines = result.output.split("\n")
    init_lines = [ln for ln in lines if ln.strip().startswith("init")]
    assert len(init_lines) == 0


def test_start_quick_creates_files(tmp_path: Path) -> None:
    """binex start --quick creates workflow.yaml, .env, .gitignore in cwd."""
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Inputs: project_name (default) -> provider 1 (ollama) -> model (default)
        result = runner.invoke(cli, ["start", "--quick"], input="\n1\n\n")
    finally:
        os.chdir(old_cwd)
    assert result.exit_code == 0, result.output
    assert (tmp_path / "workflow.yaml").exists()
    assert (tmp_path / ".env").exists()
    assert (tmp_path / ".gitignore").exists()

    wf = (tmp_path / "workflow.yaml").read_text()
    assert "planner" in wf
    assert "researcher" in wf
    assert "writer" in wf


def test_start_quick_nonempty_dir_abort(tmp_path: Path) -> None:
    """binex start --quick aborts if user declines in non-empty dir."""
    (tmp_path / "existing.txt").write_text("hello")
    runner = CliRunner()
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(cli, ["start", "--quick"], input="n\n")
    finally:
        os.chdir(old_cwd)
    assert "abort" in result.output.lower() or result.exit_code == 0
    assert not (tmp_path / "workflow.yaml").exists()
