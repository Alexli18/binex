"""Tests for binex eval CLI commands (T013, T018)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from binex.cli.eval_cmd import eval_group
from binex.eval.models import EvalCaseResult, EvalResult
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_stores():
    return InMemoryExecutionStore(), InMemoryArtifactStore()


def _make_result(verdict: str = "pass") -> EvalResult:
    from datetime import UTC, datetime
    return EvalResult(
        suite_name="test-suite",
        suite_path="/path/suite.yaml",
        executed_at=datetime.now(UTC),
        total=1,
        passed=1 if verdict == "pass" else 0,
        failed=1 if verdict == "fail" else 0,
        no_baseline=1 if verdict == "no_baseline" else 0,
        total_cost=0.0,
        cases=[EvalCaseResult(case_id="c1", verdict=verdict, run_id="run_abc")],
    )


@pytest.fixture
def suite_file(tmp_path: Path) -> Path:
    wf = tmp_path / "wf.yaml"
    wf.write_text(
        textwrap.dedent("""\
        name: test
        agents:
          worker:
            agent: local://echo
        nodes:
          - id: worker
        """)
    )
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        textwrap.dedent(f"""\
        name: test-suite
        workflow: {wf}
        cases:
          - id: c1
        """)
    )
    return suite


class TestEvalRunCommand:
    def test_exit_0_on_all_pass(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("pass")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file)])
        assert result.exit_code == 0

    def test_exit_1_on_fail(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("fail")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file)])
        assert result.exit_code == 1

    def test_exit_0_on_no_baseline_without_strict(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("no_baseline")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file)])
        assert result.exit_code == 0

    def test_exit_1_on_no_baseline_with_strict(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("no_baseline")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file), "--strict-baseline"])
        assert result.exit_code == 1

    def test_json_output(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("pass")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["suite_name"] == "test-suite"

    def test_github_format_annotations_on_fail(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("fail")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file), "--format", "github"])
        assert "::error" in result.output

    def test_github_format_warnings_on_no_baseline(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch(
                "binex.cli.eval_cmd.run_suite",
                new=AsyncMock(return_value=_make_result("no_baseline")),
            ):
                result = runner.invoke(eval_group, ["run", str(suite_file), "--format", "github"])
        assert "::warning" in result.output

    def test_exit_2_on_invalid_suite(self, tmp_path: Path):
        runner = CliRunner()
        suite = tmp_path / "bad.yaml"
        suite.write_text("invalid: yaml: [\n")
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            result = runner.invoke(eval_group, ["run", str(suite)])
        assert result.exit_code == 2

    def test_exit_2_on_missing_suite_file(self, tmp_path: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            result = runner.invoke(eval_group, ["run", str(tmp_path / "missing.yaml")])
        assert result.exit_code == 2


class TestEvalBlessCommand:
    def test_bless_all_cases(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()

        async def _mock_list_runs(*a, **kw):
            from binex.models.execution import RunSummary
            return [
                RunSummary(
                    run_id="run_abc",
                    workflow_name="test-suite",
                    status="completed",
                    total_nodes=1,
                    eval_suite_id="test-suite",
                    eval_case_id="c1",
                )
            ]

        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch.object(es, "list_runs", new=_mock_list_runs):
                result = runner.invoke(eval_group, ["bless", str(suite_file)])
        assert result.exit_code == 0

    def test_bless_outputs_blessed_info(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()

        async def _mock_list_runs(*a, **kw):
            from binex.models.execution import RunSummary
            return [
                RunSummary(
                    run_id="run_xyz",
                    workflow_name="test-suite",
                    status="completed",
                    total_nodes=1,
                    eval_suite_id="test-suite",
                    eval_case_id="c1",
                )
            ]

        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            with patch.object(es, "list_runs", new=_mock_list_runs):
                result = runner.invoke(eval_group, ["bless", str(suite_file)])
        assert "c1" in result.output or "run_xyz" in result.output


class TestEvalBaselinesCommand:
    def test_baselines_exit_0_always(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            result = runner.invoke(eval_group, ["baselines", str(suite_file)])
        assert result.exit_code == 0

    def test_baselines_json_output(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            result = runner.invoke(eval_group, ["baselines", str(suite_file), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "baselines" in data

    def test_baselines_shows_missing_marker(self, suite_file: Path):
        runner = CliRunner()
        es, ats = _make_stores()
        with patch("binex.cli.eval_cmd._get_stores", return_value=(es, ats)):
            result = runner.invoke(eval_group, ["baselines", str(suite_file)])
        # Should show that c1 has no baseline
        assert result.exit_code == 0
        assert "c1" in result.output
