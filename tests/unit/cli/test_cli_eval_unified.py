"""`binex eval golden` accepts a blessed suite baseline, and the flags line up.

Two halves of #119 as they appear on the command line: a baseline blessed with
`binex eval bless` should be usable as a golden run without pasting its id, and
`--json` should mean the same thing across the group.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class _Store:
    def __init__(self, baselines: dict[str, dict[str, str]]) -> None:
        self._baselines = baselines

    async def get_baselines(self, suite_name: str) -> dict[str, str]:
        return self._baselines.get(suite_name, {})

    async def close(self) -> None:
        return None


def _invoke(runner: CliRunner, *args: str, baselines=None, report=None):
    stores = (_Store(baselines or {}), object())
    with (
        patch("binex.cli.eval_cmd._get_stores", return_value=stores),
        patch("binex.eval.golden.run_eval", new_callable=AsyncMock) as run_eval,
    ):
        run_eval.return_value = report
        result = runner.invoke(cli, ["eval", "golden", *args])
    return result, run_eval


def _report():
    from binex.eval.golden import EvalReport

    # `passed` is derived, not a field.
    return EvalReport(
        run_id="run_new", run_status="completed", baseline_run_id="run_blessed",
        node_errors=[], divergences=[],
    )


def test_suite_case_reference_resolves_to_the_blessed_run(runner: CliRunner):
    result, run_eval = _invoke(
        runner, "examples/simple.yaml", "--baseline", "my-suite:happy",
        baselines={"my-suite": {"happy": "run_blessed"}}, report=_report(),
    )

    assert result.exit_code == 0
    assert run_eval.call_args.kwargs["baseline"] == "run_blessed"


def test_a_bare_run_id_is_passed_through(runner: CliRunner):
    result, run_eval = _invoke(
        runner, "examples/simple.yaml", "--baseline", "run_abc123",
        report=_report(),
    )

    assert result.exit_code == 0
    assert run_eval.call_args.kwargs["baseline"] == "run_abc123"


def test_an_unblessed_case_exits_2_with_a_pointer_to_bless(runner: CliRunner):
    result, run_eval = _invoke(
        runner, "examples/simple.yaml", "--baseline", "my-suite:missing",
        baselines={"my-suite": {"happy": "run_blessed"}},
    )

    assert result.exit_code == 2
    assert "missing" in result.output
    assert "bless" in result.output
    run_eval.assert_not_called()


@pytest.mark.parametrize("flag", ["--json", "--json-output"])
def test_both_json_spellings_work(runner: CliRunner, flag: str):
    """`--json` is the group-wide spelling; `--json-output` stays as an alias."""
    import json

    result, _ = _invoke(runner, "examples/simple.yaml", flag, report=_report())

    assert result.exit_code == 0
    assert json.loads(result.output)["run_id"] == "run_new"


def test_help_documents_the_suite_case_form(runner: CliRunner):
    result = runner.invoke(cli, ["eval", "golden", "--help"])

    assert result.exit_code == 0
    assert "SUITE:CASE" in result.output
