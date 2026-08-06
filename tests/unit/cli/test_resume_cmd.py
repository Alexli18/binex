"""Tests for the `binex resume` CLI command (cli/resume.py).

The ResumeEngine itself is covered in tests/unit/runtime/test_resume.py;
here we pin the CLI layer: store guards, output formats, exit codes.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from binex.cli.resume import resume_cmd
from binex.models.execution import RunSummary
from binex.runtime.resume import ResumeResult
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _summary(**kwargs) -> RunSummary:
    defaults = dict(
        run_id="run-child",
        workflow_name="wf",
        status="completed",
        total_nodes=3,
        completed_nodes=3,
        resumed_from="run-parent",
    )
    defaults.update(kwargs)
    return RunSummary(**defaults)


def _result(**kwargs) -> ResumeResult:
    defaults = dict(summary=_summary(), resumed_nodes=1, cached_nodes=2, warnings=[])
    defaults.update(kwargs)
    return ResumeResult(**defaults)


def _patch_run_resume(result=None, error=None):
    mock = AsyncMock(return_value=result)
    if error is not None:
        mock.side_effect = error
    return patch("binex.cli.resume._run_resume", mock)


# ---------------------------------------------------------------------------
# Store guards (real _run_resume against in-memory stores)
# ---------------------------------------------------------------------------


def test_resume_unknown_run_exits_1_with_error():
    stores = (InMemoryExecutionStore(), InMemoryArtifactStore())

    with patch("binex.cli.resume.get_stores", return_value=stores):
        result = CliRunner().invoke(resume_cmd, ["run-ghost"])

    assert result.exit_code == 1
    assert "Run 'run-ghost' not found" in result.output


def test_resume_run_without_workflow_path_exits_1():
    exec_store = InMemoryExecutionStore()
    stores = (exec_store, InMemoryArtifactStore())
    import asyncio

    asyncio.run(exec_store.create_run(
        _summary(run_id="run-nopath", workflow_path=None, status="failed")
    ))

    with patch("binex.cli.resume.get_stores", return_value=stores):
        result = CliRunner().invoke(resume_cmd, ["run-nopath"])

    assert result.exit_code == 1
    assert "no recorded workflow_path" in result.output


# ---------------------------------------------------------------------------
# Presentation layer (mocked _run_resume)
# ---------------------------------------------------------------------------


def test_resume_text_output_and_exit_0_on_completed():
    with _patch_run_resume(_result()):
        result = CliRunner().invoke(resume_cmd, ["run-parent"])

    assert result.exit_code == 0
    assert "Resume Run ID: run-child" in result.output
    assert "Resumed from: run-parent" in result.output
    assert "Nodes: 3/3 completed (2 cached, 1 re-run)" in result.output


def test_resume_failed_status_exits_1():
    with _patch_run_resume(
        _result(summary=_summary(status="failed", completed_nodes=2, failed_nodes=1))
    ):
        result = CliRunner().invoke(resume_cmd, ["run-parent"])

    assert result.exit_code == 1
    assert "Failed: 1" in result.output


def test_resume_json_output_includes_node_counts():
    with _patch_run_resume(_result()):
        result = CliRunner().invoke(resume_cmd, ["run-parent", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run_id"] == "run-child"
    assert data["resumed_nodes"] == 1
    assert data["cached_nodes"] == 2


def test_resume_prints_warnings_with_marker():
    with _patch_run_resume(_result(warnings=["topology drift detected"])):
        result = CliRunner().invoke(resume_cmd, ["run-parent"])

    assert "⚠ topology drift detected" in result.output


def test_resume_cost_line_only_when_positive():
    with _patch_run_resume(_result(summary=_summary(total_cost=0.1234))):
        result = CliRunner().invoke(resume_cmd, ["run-parent"])

    assert "Cost (cumulative): $0.1234" in result.output


def test_resume_forwards_from_and_force_flags():
    mock = AsyncMock(return_value=_result())

    with patch("binex.cli.resume._run_resume", mock):
        CliRunner().invoke(resume_cmd, ["run-parent", "--from", "step3", "--force"])

    mock.assert_awaited_once_with("run-parent", "step3", True)
