"""Tests for scaffold workflow subcommand (T022-T024)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from binex.cli.main import cli
from binex.cli.dsl_parser import parse_dsl
from binex.cli.scaffold import _interactive_node_config


class TestScaffoldWorkflowNoInteractive:
    """T022-T023: scaffold workflow with --no-interactive."""

    def test_scaffold_workflow_no_interactive(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "workflow", "--no-interactive", "--name", "out.yaml", "A -> B -> C"],
            )
            assert result.exit_code == 0, result.output
            path = Path("out.yaml")
            assert path.exists()
            data = yaml.safe_load(path.read_text())
            assert "nodes" in data
            assert "A" in data["nodes"]
            assert "B" in data["nodes"]
            assert "C" in data["nodes"]
            # Check depends_on
            assert data["nodes"]["B"]["depends_on"] == ["A"]
            assert data["nodes"]["C"]["depends_on"] == ["B"]
            # Check agent is local://echo for non-interactive
            assert data["nodes"]["A"]["agent"] == "local://echo"

    def test_scaffold_workflow_outputs_have_refs(self) -> None:
        """Nodes with dependencies should reference upstream outputs."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "workflow", "--no-interactive", "--name", "w.yaml", "A -> B"],
            )
            assert result.exit_code == 0, result.output
            data = yaml.safe_load(Path("w.yaml").read_text())
            # B's inputs should reference A's output
            b_inputs = data["nodes"]["B"]["inputs"]
            assert any("${A." in str(v) or "${node." in str(v) for v in b_inputs.values()), \
                f"B inputs should reference A output, got {b_inputs}"


class TestScaffoldWorkflowListPatterns:
    """T024: --list-patterns."""

    def test_scaffold_workflow_list_patterns(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["scaffold", "workflow", "--list-patterns"])
        assert result.exit_code == 0
        # Should show pattern names
        assert "linear" in result.output
        assert "diamond" in result.output
        assert "fan-out" in result.output
        assert "fan-in" in result.output


class TestScaffoldWorkflowPattern:
    """T022: --pattern flag."""

    def test_scaffold_workflow_pattern(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "workflow", "--pattern", "diamond", "--no-interactive", "--name", "d.yaml"],
            )
            assert result.exit_code == 0, result.output
            data = yaml.safe_load(Path("d.yaml").read_text())
            assert len(data["nodes"]) == 4

    def test_scaffold_workflow_unknown_pattern(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scaffold", "workflow", "--pattern", "nonexistent", "--no-interactive"],
        )
        assert result.exit_code != 0


class TestScaffoldWorkflowEnv:
    """T022: --env flag."""

    def test_scaffold_workflow_with_env(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                cli,
                ["scaffold", "workflow", "--no-interactive", "--env", "--name", "w.yaml", "A -> B"],
            )
            assert result.exit_code == 0, result.output
            assert Path(".env.example").exists()


class TestScaffoldWorkflowInvalidDSL:
    """Validation errors surface in CLI."""

    def test_scaffold_workflow_invalid_dsl(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scaffold", "workflow", "--no-interactive", "-> ->"],
        )
        assert result.exit_code != 0

    def test_scaffold_workflow_no_dsl_no_pattern(self) -> None:
        """No DSL and no --pattern should error."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["scaffold", "workflow", "--no-interactive"],
        )
        assert result.exit_code != 0


class TestScaffoldInteractiveAgentUri:
    """BUG-003/004: agent URI construction in interactive mode."""

    def test_gemini_model_no_double_prefix(self) -> None:
        """BUG-004: gemini provider + gemini/model should NOT produce
        llm://gemini/gemini/model (double prefix)."""
        parsed = parse_dsl(["A"])
        # Simulate: user picks gemini (4), accepts default model
        with patch("click.echo"), \
             patch("click.prompt", side_effect=["4", "", "do stuff"]):
            configs = _interactive_node_config(parsed)

        uri = configs["A"]["agent"]
        # Should be llm://gemini/gemini-2.0-flash, NOT llm://gemini/gemini/gemini-2.0-flash
        assert "gemini/gemini/" not in uri
        assert uri.startswith("llm://")

    def test_provider_switch_resets_model_default(self) -> None:
        """BUG-003: switching provider should reset model default,
        not carry over the previous provider's model."""
        parsed = parse_dsl(["A -> B"])
        # Node A: gemini (4), custom model "gemini/gemini-2.5-flash", system_prompt
        # Node B: ollama (1), press Enter for model (should get ollama default), system_prompt
        with patch("click.echo"), \
             patch("click.prompt", side_effect=[
                 "4", "gemini/gemini-2.5-flash", "plan",  # A: gemini
                 "1", "", "research",                       # B: switch to ollama
             ]):
            configs = _interactive_node_config(parsed)

        uri_b = configs["B"]["agent"]
        # B should use ollama default model, not gemini model
        assert "ollama" in uri_b
        assert "gemini" not in uri_b

    def test_same_provider_keeps_previous_model(self) -> None:
        """When staying on the same provider, previous model is reused as default."""
        parsed = parse_dsl(["A -> B"])
        # Node A: ollama (1), custom model "ollama/mistral", system_prompt
        # Node B: ollama (Enter=same), same model explicitly, system_prompt
        with patch("click.echo"), \
             patch("click.prompt", side_effect=[
                 "1", "ollama/mistral", "plan",       # A: ollama + custom model
                 "", "ollama/mistral", "research",     # B: same provider, same model
             ]):
            configs = _interactive_node_config(parsed)

        # Both should have same model
        assert "mistral" in configs["B"]["agent"]

    def test_openai_model_no_prefix_stripping(self) -> None:
        """OpenAI has agent_prefix='llm://' (no provider subpath),
        so model like 'gpt-4o' should produce 'llm://gpt-4o'."""
        parsed = parse_dsl(["A"])
        with patch("click.echo"), \
             patch("click.prompt", side_effect=["2", "gpt-4o", "plan"]):
            configs = _interactive_node_config(parsed)

        assert configs["A"]["agent"] == "llm://gpt-4o"
