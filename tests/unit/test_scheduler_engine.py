"""Tests for SchedulerEngine — tick, skip, rescan, scan_directory."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from binex.scheduler.models import ScheduledWorkflow, SchedulerState


# --- scan_directory tests ---


class TestScanDirectory:
    """Tests for scan_directory() — discovers workflows with schedule field."""

    def _write_workflow(self, path: Path, name: str, schedule: str | None = None):
        data: dict = {"name": name, "nodes": {"a": {"agent": "local://echo", "outputs": ["r"]}}}
        if schedule is not None:
            data["schedule"] = schedule
        path.write_text(yaml.dump(data))

    def test_finds_workflow_with_schedule(self, tmp_path: Path):
        from binex.scheduler.engine import scan_directory

        wf = tmp_path / "test.yaml"
        self._write_workflow(wf, "scheduled-wf", "*/5 * * * *")

        results = scan_directory(tmp_path)
        assert len(results) == 1
        assert results[0].name == "scheduled-wf"
        assert results[0].schedule == "*/5 * * * *"
        assert results[0].path == str(wf)

    def test_ignores_workflow_without_schedule(self, tmp_path: Path):
        from binex.scheduler.engine import scan_directory

        self._write_workflow(tmp_path / "no-sched.yaml", "plain-wf")

        results = scan_directory(tmp_path)
        assert len(results) == 0

    def test_finds_multiple_workflows(self, tmp_path: Path):
        from binex.scheduler.engine import scan_directory

        self._write_workflow(tmp_path / "a.yaml", "wf-a", "0 * * * *")
        self._write_workflow(tmp_path / "b.yml", "wf-b", "0 9 * * 1-5")
        self._write_workflow(tmp_path / "c.yaml", "wf-c")  # no schedule

        results = scan_directory(tmp_path)
        names = {r.name for r in results}
        assert names == {"wf-a", "wf-b"}

    def test_scans_subdirectories(self, tmp_path: Path):
        from binex.scheduler.engine import scan_directory

        sub = tmp_path / "subdir"
        sub.mkdir()
        self._write_workflow(sub / "nested.yaml", "nested-wf", "*/10 * * * *")

        results = scan_directory(tmp_path)
        assert len(results) == 1
        assert results[0].name == "nested-wf"

    def test_skips_invalid_yaml(self, tmp_path: Path):
        from binex.scheduler.engine import scan_directory

        (tmp_path / "bad.yaml").write_text(": invalid: yaml: [")
        self._write_workflow(tmp_path / "good.yaml", "good-wf", "*/5 * * * *")

        results = scan_directory(tmp_path)
        assert len(results) == 1


# --- SchedulerEngine tests ---


class TestSchedulerEngineInit:
    """Tests for SchedulerEngine initialization."""

    def test_init_with_workflows(self):
        from binex.scheduler.engine import SchedulerEngine

        workflows = [
            ScheduledWorkflow(
                name="wf-1",
                path="/tmp/wf1.yaml",
                schedule="*/5 * * * *",
                next_run=datetime.now(UTC),
            ),
        ]
        engine = SchedulerEngine(workflows=workflows, state=SchedulerState())
        assert len(engine.workflows) == 1

    def test_init_empty(self):
        from binex.scheduler.engine import SchedulerEngine

        engine = SchedulerEngine(workflows=[], state=SchedulerState())
        assert len(engine.workflows) == 0


class TestSchedulerEngineTick:
    """Tests for _tick — due workflows get executed, not-due skipped."""

    @pytest.mark.asyncio
    async def test_due_workflow_gets_executed(self):
        from binex.scheduler.engine import SchedulerEngine

        past = datetime.now(UTC) - timedelta(minutes=1)
        wf = ScheduledWorkflow(
            name="due-wf", path="/tmp/wf.yaml", schedule="*/5 * * * *", next_run=past,
        )
        engine = SchedulerEngine(workflows=[wf], state=SchedulerState())
        engine._execute_workflow = AsyncMock()

        await engine._tick()

        engine._execute_workflow.assert_called_once_with(wf)

    @pytest.mark.asyncio
    async def test_not_due_workflow_not_executed(self):
        from binex.scheduler.engine import SchedulerEngine

        future = datetime.now(UTC) + timedelta(hours=1)
        wf = ScheduledWorkflow(
            name="future-wf", path="/tmp/wf.yaml", schedule="*/5 * * * *", next_run=future,
        )
        engine = SchedulerEngine(workflows=[wf], state=SchedulerState())
        engine._execute_workflow = AsyncMock()

        await engine._tick()

        engine._execute_workflow.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_when_already_running(self):
        from binex.scheduler.engine import SchedulerEngine

        past = datetime.now(UTC) - timedelta(minutes=1)
        wf = ScheduledWorkflow(
            name="running-wf", path="/tmp/wf.yaml", schedule="*/5 * * * *", next_run=past,
        )
        engine = SchedulerEngine(workflows=[wf], state=SchedulerState())
        engine._execute_workflow = AsyncMock()
        # Simulate already running
        engine._running_tasks["running-wf"] = AsyncMock()

        await engine._tick()

        engine._execute_workflow.assert_not_called()
        # Should record skip
        assert len(engine.state.history) == 1
        assert engine.state.history[0].status == "skipped"
        assert engine.state.history[0].reason == "previous_still_running"


class TestSchedulerEngineSecondsToNextRun:
    """Tests for _seconds_to_next_run helper."""

    def test_returns_positive_for_future(self):
        from binex.scheduler.engine import SchedulerEngine

        future = datetime.now(UTC) + timedelta(seconds=120)
        wf = ScheduledWorkflow(
            name="wf", path="/tmp/wf.yaml", schedule="*/5 * * * *", next_run=future,
        )
        engine = SchedulerEngine(workflows=[wf], state=SchedulerState())
        secs = engine._seconds_to_next_run()
        assert 0 < secs <= 120

    def test_returns_zero_for_past(self):
        from binex.scheduler.engine import SchedulerEngine

        past = datetime.now(UTC) - timedelta(minutes=5)
        wf = ScheduledWorkflow(
            name="wf", path="/tmp/wf.yaml", schedule="*/5 * * * *", next_run=past,
        )
        engine = SchedulerEngine(workflows=[wf], state=SchedulerState())
        secs = engine._seconds_to_next_run()
        assert secs == 0

    def test_returns_max_for_empty(self):
        from binex.scheduler.engine import SchedulerEngine

        engine = SchedulerEngine(workflows=[], state=SchedulerState())
        secs = engine._seconds_to_next_run()
        assert secs == 60  # default poll interval
