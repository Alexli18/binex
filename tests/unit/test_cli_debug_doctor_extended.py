"""Extended tests for debug.py and doctor.py — covers --rich paths and run_checks."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from binex.cli.debug import debug_cmd
from binex.cli.doctor import (
    STATUS_ICONS,
    _check_http_service,
    doctor_cmd,
    run_checks,
)
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

RUN_ID = "run-ext-001"
TRACE_ID = "trace-ext-001"
NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC)


def _make_stores():
    """Create stores with a completed run."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    import asyncio

    async def _populate():
        run = RunSummary(
            run_id=RUN_ID, workflow_name="test-wf", status="completed",
            started_at=NOW, completed_at=NOW + timedelta(seconds=2),
            total_nodes=2, completed_nodes=2,
        )
        await exec_store.create_run(run)
        rec1 = ExecutionRecord(
            id="rec-1", run_id=RUN_ID, task_id="step_a",
            agent_id="llm://gpt-4", status=TaskStatus.COMPLETED,
            latency_ms=100, trace_id=TRACE_ID, prompt="Plan",
            output_artifact_refs=["art-1"],
        )
        rec2 = ExecutionRecord(
            id="rec-2", run_id=RUN_ID, task_id="step_b",
            agent_id="llm://gpt-4", status=TaskStatus.COMPLETED,
            latency_ms=200, trace_id=TRACE_ID, prompt="Execute",
            input_artifact_refs=["art-1"], output_artifact_refs=["art-2"],
        )
        await exec_store.record(rec1)
        await exec_store.record(rec2)
        art1 = Artifact(
            id="art-1", run_id=RUN_ID, type="result", content="plan",
            lineage=Lineage(produced_by="step_a"),
        )
        art2 = Artifact(
            id="art-2", run_id=RUN_ID, type="result", content="final",
            lineage=Lineage(produced_by="step_b", derived_from=["art-1"]),
        )
        await art_store.store(art1)
        await art_store.store(art2)

    asyncio.run(_populate())
    return exec_store, art_store


# ---------------------------------------------------------------------------
# debug.py — --rich with rich installed
# ---------------------------------------------------------------------------


class TestDebugRichOutput:
    def test_rich_output_renders(self):
        """--rich flag renders via format_debug_report_rich."""
        stores = _make_stores()
        with patch("binex.cli.debug._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, [RUN_ID, "--rich"])

        assert result.exit_code == 0, result.output
        # Rich output should contain run_id and node names
        assert RUN_ID in result.output or "step_a" in result.output

    def test_rich_with_node_filter(self):
        """--rich --node step_a filters to single node."""
        stores = _make_stores()
        with patch("binex.cli.debug._get_stores", return_value=stores):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, [RUN_ID, "--rich", "--node", "step_a"])

        assert result.exit_code == 0, result.output
        assert "step_a" in result.output

    def test_rich_import_error_falls_back_to_plain(self):
        """If rich module is unavailable, --rich falls back to plain text."""
        stores = _make_stores()
        with (
            patch("binex.cli.debug._get_stores", return_value=stores),
            patch.dict("sys.modules", {"binex.trace.debug_rich": None}),
        ):
            runner = CliRunner()
            result = runner.invoke(debug_cmd, [RUN_ID, "--rich"])

        assert result.exit_code == 0
        assert "Debug:" in result.output


# ---------------------------------------------------------------------------
# doctor.py — _check_http_service generic Exception
# ---------------------------------------------------------------------------


class TestCheckHttpServiceGenericError:
    def test_generic_exception_returns_error(self):
        """Non-httpx exception returns status=error with str(e)."""
        with patch("httpx.get", side_effect=RuntimeError("unexpected")):
            result = _check_http_service("http://localhost:9999/health", "Broken")
        assert result["status"] == "error"
        assert "unexpected" in result["detail"]


# ---------------------------------------------------------------------------
# doctor.py — run_checks integration
# ---------------------------------------------------------------------------


class TestRunChecks:
    def test_run_checks_returns_list(self):
        """run_checks returns a list of check dicts with expected keys."""
        mock_resp = MagicMock(status_code=200)
        settings = MagicMock()
        settings.store_path = "/tmp/binex-test-store"

        with (
            patch("shutil.which", return_value="/usr/bin/docker"),
            patch("binex.cli.doctor.subprocess.run",
                  return_value=MagicMock(returncode=0)),
            patch("binex.cli.doctor.httpx.get", return_value=mock_resp),
            patch("binex.settings.Settings", return_value=settings),
            patch("pathlib.Path.exists", return_value=True),
        ):
            checks = run_checks()

        assert isinstance(checks, list)
        assert len(checks) >= 9  # docker + docker daemon + 7 services + store
        for check in checks:
            assert "name" in check
            assert "status" in check
            assert "detail" in check

    def test_run_checks_with_failures(self):
        """run_checks handles mixed healthy/unhealthy services."""
        settings = MagicMock()
        settings.store_path = "/tmp/nonexistent"

        with (
            patch("shutil.which", return_value=None),
            patch("binex.cli.doctor.subprocess.run",
                  side_effect=FileNotFoundError),
            patch("binex.cli.doctor.httpx.get",
                  side_effect=httpx.ConnectError("refused")),
            patch("binex.settings.Settings", return_value=settings),
            patch("pathlib.Path.exists", return_value=False),
        ):
            checks = run_checks()

        assert isinstance(checks, list)
        statuses = {c["status"] for c in checks}
        assert "unreachable" in statuses or "error" in statuses or "missing" in statuses


# ---------------------------------------------------------------------------
# doctor.py — STATUS_ICONS coverage
# ---------------------------------------------------------------------------


class TestStatusIcons:
    def test_all_statuses_have_icons(self):
        expected = {"ok", "missing", "error", "degraded", "unreachable", "timeout", "not initialized"}
        assert set(STATUS_ICONS.keys()) == expected


# ---------------------------------------------------------------------------
# doctor.py — doctor_cmd edge cases
# ---------------------------------------------------------------------------


class TestDoctorCmdEdgeCases:
    def test_doctor_with_degraded_status(self):
        """'degraded' and 'timeout' statuses don't trigger has_errors → exit 0."""
        checks = [
            {"name": "Ollama", "status": "degraded", "detail": "503"},
            {"name": "Store", "status": "timeout", "detail": "timed out"},
            {"name": "Other", "status": "not initialized", "detail": "will be created"},
        ]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(doctor_cmd)
        assert result.exit_code == 0
        assert "All checks passed" in result.output

    def test_doctor_unknown_status_uses_question_mark(self):
        """Unknown status falls back to '?' icon."""
        checks = [{"name": "Custom", "status": "weird", "detail": "strange"}]
        with patch("binex.cli.doctor.run_checks", return_value=checks):
            runner = CliRunner()
            result = runner.invoke(doctor_cmd)
        assert "?" in result.output

    def test_docker_timeout_returns_error(self):
        """subprocess.TimeoutExpired returns error status."""
        with patch(
            "binex.cli.doctor.subprocess.run",
            side_effect=subprocess.TimeoutExpired("docker", 10),
        ):
            from binex.cli.doctor import _check_docker_running
            result = _check_docker_running()
        assert result["status"] == "error"
        assert "cannot connect" in result["detail"]
