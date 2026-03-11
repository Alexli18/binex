"""Tests for custom workflow wizard in `binex start`."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from binex.cli.start import _step_mode_topology, start_cmd


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
