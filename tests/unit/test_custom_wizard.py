"""Tests for custom workflow wizard in `binex start`."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from binex.cli.start import (
    _get_bundled_prompt_list,
    _select_prompt,
    _step_mode_topology,
    start_cmd,
)


class TestStepModeTopology:
    """Step-by-step topology builder."""

    def test_simple_linear(self):
        """Three nodes in sequence."""
        inputs = iter(["planner", "researcher", "writer", "done"])
        result = _step_mode_topology(input_fn=lambda prompt: next(inputs))
        assert result == "planner -> researcher -> writer"

    def test_parallel_nodes(self):
        """Fan-out: one node followed by two parallel."""
        inputs = iter(["start", "a, b", "end", "done"])
        result = _step_mode_topology(input_fn=lambda prompt: next(inputs))
        assert result == "start -> a, b -> end"

    def test_single_node(self):
        """Only one node then done."""
        inputs = iter(["solo", "done"])
        result = _step_mode_topology(input_fn=lambda prompt: next(inputs))
        assert result == "solo"


class TestCustomTemplateHybrid:
    """Custom template offers DSL or step mode."""

    def test_dsl_mode_still_works(self, tmp_path, monkeypatch):
        """Entering DSL directly works as before."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=5, mode=1(dsl), topology="X -> Y", user_input=n, ollama, default, name, run=n
        result = runner.invoke(
            start_cmd,
            input="5\n1\nX -> Y\nn\n1\n\nhybrid-dsl\nn\n",
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "hybrid-dsl" / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"X", "Y"}

    def test_step_mode_works(self, tmp_path, monkeypatch):
        """Choosing step launches interactive builder."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=5, mode=2(step), nodes: A -> B -> done, user_input=n, ollama, default, name, run=n
        result = runner.invoke(
            start_cmd,
            input="5\n2\nA\nB\ndone\nn\n1\n\nhybrid-step\nn\n",
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "hybrid-step" / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"A", "B"}


class TestPromptSelection:
    """Prompt picker: bundled list + custom text + file path."""

    def test_get_bundled_prompt_list(self):
        """Should return list of (filename, first_line) tuples."""
        prompts = _get_bundled_prompt_list()
        assert len(prompts) == 14
        assert all(isinstance(p, tuple) and len(p) == 2 for p in prompts)

    def test_select_bundled_prompt(self):
        """Choosing a number selects bundled prompt as file:// reference."""
        inputs = iter(["1"])
        result = _select_prompt(node_id="test", input_fn=lambda prompt: next(inputs))
        assert result.startswith("file://prompts/")
        assert result.endswith(".md")

    def test_select_custom_text(self):
        """Choosing 'custom text' option returns entered text."""
        prompts = _get_bundled_prompt_list()
        custom_option = str(len(prompts) + 1)
        inputs = iter([custom_option, "You are a helpful bot"])
        result = _select_prompt(node_id="test", input_fn=lambda prompt: next(inputs))
        assert result == "You are a helpful bot"

    def test_select_file_path(self):
        """Choosing 'file path' option returns file:// reference."""
        prompts = _get_bundled_prompt_list()
        file_option = str(len(prompts) + 2)
        inputs = iter([file_option, "/path/to/my-prompt.md"])
        result = _select_prompt(node_id="test", input_fn=lambda prompt: next(inputs))
        assert result == "file:///path/to/my-prompt.md"


from binex.cli.start import _configure_advanced_params


class TestAdvancedParams:
    """Optional advanced parameter configuration."""

    def test_budget_only(self):
        inputs = iter(["0.50", "", "", "", ""])
        result = _configure_advanced_params(input_fn=lambda prompt: next(inputs))
        assert result["budget"] == {"max_cost": 0.50}
        assert "retry_policy" not in result
        assert "deadline_ms" not in result
        assert "config" not in result

    def test_all_params(self):
        inputs = iter(["1.00", "3", "exponential", "30", "0.7", "2000"])
        result = _configure_advanced_params(input_fn=lambda prompt: next(inputs))
        assert result["budget"] == {"max_cost": 1.00}
        assert result["retry_policy"] == {"max_retries": 3, "backoff": "exponential"}
        assert result["deadline_ms"] == 30000
        assert result["config"] == {"temperature": 0.7, "max_tokens": 2000}

    def test_skip_all(self):
        """Empty inputs skip all optional params."""
        inputs = iter(["", "", "", "", ""])
        result = _configure_advanced_params(input_fn=lambda prompt: next(inputs))
        assert result == {}
