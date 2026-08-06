"""Extended tests for cli/run.py — covers validation errors, JSON output,
content truncation, LLM adapter registration, error collection, skipped nodes,
and _parse_vars edge cases."""

from __future__ import annotations

import json
import textwrap
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.cli.run import _parse_vars
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path, content: str):
    wf = tmp_path / "wf.yaml"
    wf.write_text(textwrap.dedent(content))
    return wf


def _simple_yaml() -> str:
    return """\
        name: simple
        nodes:
          step1:
            agent: local://echo
            outputs: [out]
    """


def _cycle_yaml() -> str:
    return """\
        name: cycle-test
        nodes:
          a:
            agent: local://x
            outputs: [out]
            depends_on: [b]
          b:
            agent: local://x
            outputs: [out]
            depends_on: [a]
    """


# ---------------------------------------------------------------------------
# T1: Validation errors (cycle) => exit code 2
# ---------------------------------------------------------------------------

class TestRunValidationErrors:
    def test_run_validation_errors_exits_2(self, runner, tmp_path):
        wf = _write_yaml(tmp_path, _cycle_yaml())
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        with patch("binex.cli.run._get_stores", return_value=stores):
            result = runner.invoke(cli, ["run", str(wf)])

        assert result.exit_code == 2
        assert "Error:" in result.output


# ---------------------------------------------------------------------------
# T2-T3: JSON output flags
# ---------------------------------------------------------------------------

class TestRunJsonOutput:
    def test_run_json_output(self, runner, tmp_path):
        """--json flag produces parseable JSON with run_id and status."""
        wf = _write_yaml(tmp_path, _simple_yaml())
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        with patch("binex.cli.run._get_stores", return_value=stores):
            result = runner.invoke(cli, ["run", str(wf), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "run_id" in data
        assert "status" in data
        assert data["status"] == "completed"

    def test_run_json_verbose_includes_artifacts(self, runner, tmp_path):
        """--json -v includes an 'artifacts' key in the JSON output."""
        from binex.models.artifact import Artifact, Lineage
        from binex.models.execution import RunSummary

        wf = _write_yaml(tmp_path, _simple_yaml())
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        art = Artifact(
            id="art_step1", run_id="run_v", type="result",
            content="hello",
            lineage=Lineage(produced_by="step1", derived_from=[]),
        )

        async def _mock_run(spec, verbose=False, **kwargs):
            summary = RunSummary(
                run_id="run_v", workflow_name="simple",
                status="completed", total_nodes=1,
                completed_nodes=1,
            )
            return summary, [], [art]

        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run._run", side_effect=_mock_run),
        ):
            result = runner.invoke(cli, ["run", str(wf), "--json", "-v"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "artifacts" in data
        assert isinstance(data["artifacts"], list)
        assert len(data["artifacts"]) == 1


# ---------------------------------------------------------------------------
# T4-T5: Failed run shows tip + error details
# ---------------------------------------------------------------------------

class TestRunFailedOutput:
    def test_run_failed_shows_tip(self, runner, tmp_path):
        """A failed run prints 'Tip:' and 'binex debug' to stderr."""
        wf = _write_yaml(tmp_path, _simple_yaml())
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        from binex.models.execution import RunSummary

        async def _mock_run(spec, verbose=False, **kwargs):
            summary = RunSummary(
                run_id="run_fail_001",
                workflow_name="simple",
                status="failed",
                total_nodes=1,
                completed_nodes=0,
                failed_nodes=1,
            )
            return summary, [("step1", "kaboom")], []

        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run._run", side_effect=_mock_run),
        ):
            result = runner.invoke(cli, ["run", str(wf)])

        assert result.exit_code == 1
        assert "Tip:" in result.output
        assert "binex debug" in result.output

    def test_run_failed_shows_error_details(self, runner, tmp_path):
        """A failed run prints the per-node error messages."""
        wf = _write_yaml(tmp_path, _simple_yaml())
        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        from binex.models.execution import RunSummary

        async def _mock_run(spec, verbose=False, **kwargs):
            summary = RunSummary(
                run_id="run_fail_002",
                workflow_name="simple",
                status="failed",
                total_nodes=1,
                completed_nodes=0,
                failed_nodes=1,
            )
            return summary, [("step1", "connection refused")], []

        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run._run", side_effect=_mock_run),
        ):
            result = runner.invoke(cli, ["run", str(wf)])

        assert result.exit_code == 1
        assert "connection refused" in result.output
        assert "step1" in result.output


# ---------------------------------------------------------------------------
# T6-T8: _parse_vars
# ---------------------------------------------------------------------------

class TestParseVars:
    def test_parse_vars_valid(self):
        result = _parse_vars(("key=value", "name=Alice"))
        assert result == {"key": "value", "name": "Alice"}

    def test_parse_vars_invalid(self):
        with pytest.raises(click.BadParameter, match="expected key=value"):
            _parse_vars(("no_equals_here",))

    def test_parse_vars_value_with_equals(self):
        result = _parse_vars(("key=a=b",))
        assert result == {"key": "a=b"}
