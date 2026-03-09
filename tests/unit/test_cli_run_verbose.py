"""Tests for verbose output improvements in `binex run -v` (T027-T028)."""

from __future__ import annotations

import textwrap
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _simple_workflow_yaml() -> str:
    return textwrap.dedent("""\
        name: test-verbose
        nodes:
          fetch:
            agent: local://fetch
            outputs: [data]
          analyse:
            agent: local://analyse
            depends_on: [fetch]
            outputs: [report]
    """)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestVerboseProgressCounter:
    """T027: verbose output contains [N/total] progress counter."""

    def test_verbose_shows_progress_counter(self, runner, tmp_path):
        wf = tmp_path / "wf.yaml"
        wf.write_text(_simple_workflow_yaml())

        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
        with patch("binex.cli.run._get_stores", return_value=stores):
            result = runner.invoke(cli, ["run", str(wf), "-v"])

        # Progress counter pattern [N/total] should appear in output
        assert "[1/" in result.output
        assert "[2/" in result.output or "/2]" in result.output


class TestVerboseShowsTip:
    """T028: verbose output contains Tip when run fails."""

    def test_verbose_shows_tip_on_failure(self, runner, tmp_path):
        wf = tmp_path / "wf.yaml"
        wf.write_text(_simple_workflow_yaml())

        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

        from binex.models.execution import RunSummary

        async def _mock_run(spec, verbose=False):
            summary = RunSummary(
                run_id="run_fail_123",
                workflow_name="test-verbose",
                status="failed",
                total_nodes=2,
                completed_nodes=1,
                failed_nodes=1,
            )
            return summary, [("analyse", "boom")], []

        with (
            patch("binex.cli.run._get_stores", return_value=stores),
            patch("binex.cli.run._run", side_effect=_mock_run),
        ):
            result = runner.invoke(cli, ["run", str(wf), "-v"])

        assert "Tip:" in result.output
        assert "binex debug" in result.output

    def test_no_tip_on_success(self, runner, tmp_path):
        wf = tmp_path / "wf.yaml"
        wf.write_text(_simple_workflow_yaml())

        stores = (InMemoryExecutionStore(), InMemoryArtifactStore())
        with patch("binex.cli.run._get_stores", return_value=stores):
            result = runner.invoke(cli, ["run", str(wf)])

        assert "Tip:" not in result.output
