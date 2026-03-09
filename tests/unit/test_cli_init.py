"""Tests for `binex init` command (T013-T018)."""

from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from binex.cli.main import cli


def test_init_workflow_mode(tmp_path: Path) -> None:
    """T013: workflow mode creates workflow.yaml, .env.example, .gitignore."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # Prompts: project_name(default) -> mode=1 -> provider=2(openai) -> model(default)
        result = runner.invoke(cli, ["init"], input="\n1\n2\n\n")
        assert result.exit_code == 0, result.output

        td_path = Path(td)
        assert (td_path / "workflow.yaml").exists()
        assert (td_path / ".env.example").exists()
        assert (td_path / ".gitignore").exists()

        # workflow.yaml should have planner/researcher/writer nodes
        wf = (td_path / "workflow.yaml").read_text()
        assert "planner:" in wf
        assert "researcher:" in wf
        assert "writer:" in wf
        assert "gpt-4o" in wf  # openai default model

        # Should NOT have agent dir in workflow-only mode
        assert not (td_path / "agents").exists()
        assert not (td_path / "tests").exists()


def test_init_agent_mode(tmp_path: Path) -> None:
    """T014: agent mode creates agents/ directory in addition to base files."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # mode=2 (agent), provider=1 (ollama), model=default
        result = runner.invoke(cli, ["init"], input="\n2\n1\n\n")
        assert result.exit_code == 0, result.output

        td_path = Path(td)
        assert (td_path / "workflow.yaml").exists()
        assert (td_path / ".env.example").exists()
        assert (td_path / ".gitignore").exists()
        assert (td_path / "agents").is_dir()


def test_init_full_mode(tmp_path: Path) -> None:
    """T015: full mode creates all files including tests/ and docker-compose.yml."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # mode=3 (full), provider=3 (anthropic), model=default
        result = runner.invoke(cli, ["init"], input="\n3\n3\n\n")
        assert result.exit_code == 0, result.output

        td_path = Path(td)
        assert (td_path / "workflow.yaml").exists()
        assert (td_path / ".env.example").exists()
        assert (td_path / ".gitignore").exists()
        assert (td_path / "agents").is_dir()
        assert (td_path / "workflows").is_dir()
        assert (td_path / "tests").is_dir()
        assert (td_path / "tests" / "__init__.py").exists()
        assert (td_path / "tests" / "test_workflow.py").exists()
        assert (td_path / "docker-compose.yml").exists()


def test_init_with_name_option(tmp_path: Path) -> None:
    """T016: --name flag skips the project name prompt."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # --name provided, so first prompt skipped: mode=1, provider=1, model=default
        result = runner.invoke(cli, ["init", "--name", "my-cool-project"], input="1\n1\n\n")
        assert result.exit_code == 0, result.output

        td_path = Path(td)
        wf = (td_path / "workflow.yaml").read_text()
        assert "my-cool-project" in wf


def test_init_nonempty_dir_warning(tmp_path: Path) -> None:
    """T017: confirmation prompt when directory is not empty."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # Create a file to make dir non-empty
        Path(td, "existing.txt").write_text("hello")

        # Answer 'n' to confirmation -> should abort
        result = runner.invoke(cli, ["init"], input="n\n")
        assert result.exit_code == 0 or result.exit_code == 1
        assert "not empty" in result.output.lower() or "abort" in result.output.lower()

        # Answer 'y' to confirmation, then fill prompts
        result = runner.invoke(cli, ["init"], input="y\n\n1\n1\n\n")
        assert result.exit_code == 0, result.output
        assert (Path(td) / "workflow.yaml").exists()


def test_init_skip_provider(tmp_path: Path) -> None:
    """Provider=9 (skip) means no env var in .env.example."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # mode=1, provider=9 (skip)
        result = runner.invoke(cli, ["init"], input="\n1\n9\n")
        assert result.exit_code == 0, result.output

        td_path = Path(td)
        env_content = (td_path / ".env.example").read_text()
        # Should not contain any API key line
        assert "API_KEY" not in env_content

        # workflow.yaml should still exist but use a placeholder
        wf = (td_path / "workflow.yaml").read_text()
        assert "planner:" in wf


def test_init_provider_env_var(tmp_path: Path) -> None:
    """Provider=2 (openai) puts OPENAI_API_KEY in .env.example."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # mode=1, provider=2 (openai), model=default
        result = runner.invoke(cli, ["init"], input="\n1\n2\n\n")
        assert result.exit_code == 0, result.output

        td_path = Path(td)
        env_content = (td_path / ".env.example").read_text()
        assert "OPENAI_API_KEY" in env_content
