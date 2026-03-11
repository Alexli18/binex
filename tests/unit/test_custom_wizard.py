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


from binex.cli.start import _configure_back_edge


class TestConfigureBackEdge:
    """Back-edge (review loop) configuration."""

    def test_basic_back_edge(self):
        inputs = iter(["1", "3"])  # target choice=1 (writer), max_iterations=3
        result = _configure_back_edge(
            node_id="review",
            upstream_nodes=["writer"],
            input_fn=lambda prompt: next(inputs),
        )
        assert result["target"] == "writer"
        assert result["when"] == "${review.decision} == rejected"
        assert result["max_iterations"] == 3

    def test_multiple_upstream_choice(self):
        inputs = iter(["2", "5"])  # target=2nd upstream (researcher), max=5
        result = _configure_back_edge(
            node_id="review",
            upstream_nodes=["writer", "researcher"],
            input_fn=lambda prompt: next(inputs),
        )
        assert result["target"] == "researcher"
        assert result["max_iterations"] == 5

    def test_default_max_iterations(self):
        inputs = iter(["1", ""])  # target, empty=default 3
        result = _configure_back_edge(
            node_id="review",
            upstream_nodes=["generate"],
            input_fn=lambda prompt: next(inputs),
        )
        assert result["max_iterations"] == 3


from binex.cli.start import _configure_node


class TestConfigureNode:
    """Per-node interactive configuration."""

    def test_llm_node_basic(self):
        """LLM node returns agent URI, prompt, no back-edge."""
        inputs = iter([
            "1",          # agent type: LLM
            "1",          # provider: ollama
            "",           # model: default (will use provider default)
            "1",          # prompt: first bundled
            "n",          # back-edge: no
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="writer",
            dependencies=["planner"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"].startswith("llm://")
        assert config["system_prompt"].startswith("file://prompts/")
        assert "back_edge" not in config
        assert config["depends_on"] == ["planner"]

    def test_human_review_node(self):
        """Human review node uses human://review agent."""
        inputs = iter([
            "2",          # agent type: Human review
            "n",          # back-edge: no
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="review",
            dependencies=["writer"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"] == "human://review"

    def test_human_input_node(self):
        """Human input node uses human://input agent."""
        inputs = iter([
            "3",          # agent type: Human input
            "What is your topic?",  # prompt text
            "n",          # back-edge: no
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="ask",
            dependencies=[],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"] == "human://input"
        assert config["system_prompt"] == "What is your topic?"

    def test_a2a_node(self):
        """A2A node uses a2a:// agent."""
        inputs = iter([
            "4",                          # agent type: A2A
            "http://localhost:9000",       # endpoint
            "n",                          # back-edge: no
            "n",                          # advanced: no
        ])
        config = _configure_node(
            node_id="external",
            dependencies=["planner"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"] == "a2a://http://localhost:9000"

    def test_back_edge_config(self):
        """Human review node with back-edge."""
        inputs = iter([
            "2",          # agent type: Human review
            "y",          # back-edge: yes
            "1",          # target: first upstream node (writer)
            "3",          # max_iterations
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="review",
            dependencies=["writer"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["back_edge"]["target"] == "writer"
        assert config["back_edge"]["max_iterations"] == 3
        assert "rejected" in config["back_edge"]["when"]
