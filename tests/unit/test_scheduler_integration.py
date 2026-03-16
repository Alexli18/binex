"""Integration tests for scheduler — cross-module flows.

Tests cover:
- scan+list roundtrip (directory scan → workflow list, with registered, dedup)
- state add/remove (persistence roundtrip, multiple ops)
- engine tick+record (execute, skip, record in state history)
- YAML loading with schedule (load → validate → scan → engine flow)
- cron validation rejection (various invalid patterns)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from binex.scheduler.engine import SchedulerEngine, scan_directory
from binex.scheduler.models import ScheduledWorkflow, SchedulerState
from binex.scheduler.state import load_state, record_run, record_skip, save_state
from binex.workflow_spec.loader import load_workflow
from binex.workflow_spec.validator import validate_workflow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_wf(path: Path, name: str, schedule: str | None = None, **extra: object) -> Path:
    """Write a minimal workflow YAML file."""
    data: dict = {
        "name": name,
        "nodes": {"a": {"agent": "local://echo", "outputs": ["r"]}},
    }
    if schedule:
        data["schedule"] = schedule
    data.update(extra)
    path.write_text(yaml.dump(data))
    return path


# ===========================================================================
# 1. Scan + List Round-Trip
# ===========================================================================


class TestScanAndListRoundTrip:
    """Integration: scan directory → collect workflows → verify list."""

    def test_scan_matches_cli_list(self, tmp_path: Path):
        _write_wf(tmp_path / "a.yaml", "wf-a", "*/5 * * * *")
        _write_wf(tmp_path / "b.yaml", "wf-b", "0 9 * * *")
        _write_wf(tmp_path / "c.yaml", "wf-c")  # no schedule

        workflows = scan_directory(tmp_path)
        assert len(workflows) == 2
        names = {w.name for w in workflows}
        assert names == {"wf-a", "wf-b"}

    def test_scan_and_state_registered(self, tmp_path: Path):
        """Registered workflow from state is included in collection."""
        from binex.cli.scheduler import _collect_workflows

        _write_wf(tmp_path / "a.yaml", "wf-a", "*/5 * * * *")

        ext = tmp_path / "external" / "ext.yaml"
        ext.parent.mkdir()
        _write_wf(ext, "ext-wf", "0 12 * * *")

        state_path = tmp_path / ".binex" / "scheduler.json"
        state = SchedulerState(registered=[str(ext)])
        save_state(state, state_path)

        workflows = _collect_workflows(tmp_path, state_path)
        names = {w.name for w in workflows}
        assert "wf-a" in names
        assert "ext-wf" in names

    def test_scan_deduplicates_registered_and_scanned(self, tmp_path: Path):
        """If a file is both in scan directory and registered, it appears once."""
        from binex.cli.scheduler import _collect_workflows

        wf_file = _write_wf(tmp_path / "dup.yaml", "dup-wf", "*/10 * * * *")

        state_path = tmp_path / ".binex" / "scheduler.json"
        state = SchedulerState(registered=[str(wf_file)])
        save_state(state, state_path)

        workflows = _collect_workflows(tmp_path, state_path)
        paths = [w.path for w in workflows]
        assert paths.count(str(wf_file)) == 1

    def test_scan_subdirectories(self, tmp_path: Path):
        """Workflows in nested directories are found."""
        sub = tmp_path / "nested" / "deep"
        sub.mkdir(parents=True)
        _write_wf(sub / "inner.yaml", "inner-wf", "0 * * * *")

        workflows = scan_directory(tmp_path)
        assert len(workflows) == 1
        assert workflows[0].name == "inner-wf"

    def test_scan_yml_extension(self, tmp_path: Path):
        """Both .yaml and .yml are discovered."""
        _write_wf(tmp_path / "a.yaml", "yaml-wf", "*/5 * * * *")
        _write_wf(tmp_path / "b.yml", "yml-wf", "0 8 * * *")

        workflows = scan_directory(tmp_path)
        names = {w.name for w in workflows}
        assert names == {"yaml-wf", "yml-wf"}

    def test_scan_returns_correct_paths(self, tmp_path: Path):
        """Each workflow's path points to the correct file."""
        f = _write_wf(tmp_path / "wf.yaml", "path-wf", "*/5 * * * *")

        workflows = scan_directory(tmp_path)
        assert len(workflows) == 1
        assert workflows[0].path == str(f)

    def test_scan_next_run_is_future(self, tmp_path: Path):
        """Scanned workflows have next_run in the future."""
        _write_wf(tmp_path / "wf.yaml", "future-wf", "*/5 * * * *")

        workflows = scan_directory(tmp_path)
        assert len(workflows) == 1
        assert workflows[0].next_run > datetime.now(UTC)

    def test_collect_missing_registered_file(self, tmp_path: Path):
        """Missing registered file is skipped with warning, no crash."""
        from binex.cli.scheduler import _collect_workflows

        state_path = tmp_path / ".binex" / "scheduler.json"
        state = SchedulerState(registered=["/nonexistent/ghost.yaml"])
        save_state(state, state_path)

        workflows = _collect_workflows(tmp_path, state_path)
        assert all(w.path != "/nonexistent/ghost.yaml" for w in workflows)


# ===========================================================================
# 2. State Add/Remove Round-Trip
# ===========================================================================


class TestStateAddRemoveRoundTrip:
    """Integration: add/remove workflow to state, verify persistence."""

    def test_add_remove_roundtrip(self, tmp_path: Path):
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        state.registered.append("/tmp/wf.yaml")
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert "/tmp/wf.yaml" in loaded.registered

        loaded.registered.remove("/tmp/wf.yaml")
        save_state(loaded, state_path)

        reloaded = load_state(state_path)
        assert reloaded.registered == []

    def test_add_multiple_then_remove_one(self, tmp_path: Path):
        """Add three entries, remove the middle one, verify persistence."""
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        state.registered = ["/a.yaml", "/b.yaml", "/c.yaml"]
        save_state(state, state_path)

        loaded = load_state(state_path)
        loaded.registered.remove("/b.yaml")
        save_state(loaded, state_path)

        reloaded = load_state(state_path)
        assert reloaded.registered == ["/a.yaml", "/c.yaml"]

    def test_add_duplicate_is_preserved(self, tmp_path: Path):
        """State doesn't deduplicate — that's CLI's job."""
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        state.registered = ["/a.yaml", "/a.yaml"]
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert loaded.registered.count("/a.yaml") == 2

    def test_empty_state_roundtrip(self, tmp_path: Path):
        """Empty state serializes and deserializes correctly."""
        state_path = tmp_path / "scheduler.json"
        save_state(SchedulerState(), state_path)

        loaded = load_state(state_path)
        assert loaded.registered == []
        assert loaded.history == []

    def test_state_with_history_roundtrip(self, tmp_path: Path):
        """State with both registered and history survives roundtrip."""
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState(registered=["/wf.yaml"])
        record_run(state, "wf", "run-1", "completed", 2.0, 0.01)
        record_skip(state, "wf", "previous_still_running")
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert loaded.registered == ["/wf.yaml"]
        assert len(loaded.history) == 2
        assert loaded.history[0].status == "completed"
        assert loaded.history[1].status == "skipped"


# ===========================================================================
# 3. Engine Tick + Record
# ===========================================================================


class TestEngineTickAndRecord:
    """Integration: engine tick → execute → record in state."""

    @pytest.mark.asyncio
    async def test_tick_records_skip(self):
        past = datetime.now(UTC) - timedelta(minutes=1)
        wf = ScheduledWorkflow(
            name="test-wf", path="/tmp/wf.yaml",
            schedule="*/5 * * * *", next_run=past,
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf], state=state)
        engine._execute_workflow = AsyncMock()

        # Mark as running to trigger skip
        engine._running_tasks["test-wf"] = AsyncMock()
        await engine._tick()

        assert len(state.history) == 1
        assert state.history[0].status == "skipped"
        assert state.history[0].reason == "previous_still_running"

    @pytest.mark.asyncio
    async def test_tick_executes_due_workflow(self):
        past = datetime.now(UTC) - timedelta(minutes=1)
        wf = ScheduledWorkflow(
            name="due-wf", path="/tmp/wf.yaml",
            schedule="*/5 * * * *", next_run=past,
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf], state=state)
        engine._execute_workflow = AsyncMock()

        await engine._tick()
        engine._execute_workflow.assert_called_once_with(wf)

    @pytest.mark.asyncio
    async def test_tick_advances_next_run_on_skip(self):
        """After a skip, next_run is advanced to the future."""
        past = datetime.now(UTC) - timedelta(minutes=1)
        wf = ScheduledWorkflow(
            name="adv-wf", path="/tmp/wf.yaml",
            schedule="*/5 * * * *", next_run=past,
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf], state=state)
        engine._execute_workflow = AsyncMock()
        engine._running_tasks["adv-wf"] = AsyncMock()

        await engine._tick()

        assert wf.next_run > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_tick_multiple_workflows_mixed(self):
        """Due workflows execute, not-due ones are left alone."""
        past = datetime.now(UTC) - timedelta(minutes=1)
        future = datetime.now(UTC) + timedelta(hours=1)
        wf_due = ScheduledWorkflow(
            name="due", path="/tmp/due.yaml",
            schedule="*/5 * * * *", next_run=past,
        )
        wf_not_due = ScheduledWorkflow(
            name="notdue", path="/tmp/notdue.yaml",
            schedule="0 9 * * *", next_run=future,
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf_due, wf_not_due], state=state)
        engine._execute_workflow = AsyncMock()

        await engine._tick()

        engine._execute_workflow.assert_called_once_with(wf_due)

    @pytest.mark.asyncio
    async def test_tick_and_record_run_persist(self, tmp_path: Path):
        """Record run in state → save → load → verify."""
        state = SchedulerState()
        record_run(state, "wf", "run-1", "completed", 3.0, 0.015)

        state_path = tmp_path / "scheduler.json"
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert len(loaded.history) == 1
        entry = loaded.history[0]
        assert entry.workflow == "wf"
        assert entry.run_id == "run-1"
        assert entry.status == "completed"
        assert entry.duration_s == 3.0
        assert entry.cost == 0.015

    @pytest.mark.asyncio
    async def test_tick_skip_and_record_persist(self, tmp_path: Path):
        """Skip → record → save → load → verify skip entry."""
        past = datetime.now(UTC) - timedelta(minutes=1)
        wf = ScheduledWorkflow(
            name="skip-wf", path="/tmp/wf.yaml",
            schedule="*/5 * * * *", next_run=past,
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf], state=state)
        engine._execute_workflow = AsyncMock()
        engine._running_tasks["skip-wf"] = AsyncMock()

        await engine._tick()

        state_path = tmp_path / "scheduler.json"
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert len(loaded.history) == 1
        assert loaded.history[0].status == "skipped"
        assert loaded.history[0].workflow == "skip-wf"

    @pytest.mark.asyncio
    async def test_cleanup_finished_tasks(self):
        """Finished asyncio tasks are removed from running set."""
        wf = ScheduledWorkflow(
            name="wf", path="/tmp/wf.yaml",
            schedule="*/5 * * * *", next_run=datetime.now(UTC) + timedelta(hours=1),
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf], state=state)

        mock_task = MagicMock()
        mock_task.done.return_value = True
        engine._running_tasks["wf"] = mock_task

        engine._cleanup_finished_tasks()
        assert "wf" not in engine._running_tasks

    @pytest.mark.asyncio
    async def test_cleanup_keeps_running_tasks(self):
        """Still-running tasks are NOT removed from running set."""
        wf = ScheduledWorkflow(
            name="wf", path="/tmp/wf.yaml",
            schedule="*/5 * * * *", next_run=datetime.now(UTC) + timedelta(hours=1),
        )
        state = SchedulerState()
        engine = SchedulerEngine(workflows=[wf], state=state)

        mock_task = MagicMock()
        mock_task.done.return_value = False
        engine._running_tasks["wf"] = mock_task

        engine._cleanup_finished_tasks()
        assert "wf" in engine._running_tasks


# ===========================================================================
# 4. YAML Loading with Schedule
# ===========================================================================


class TestYAMLLoadingWithSchedule:
    """Integration: load YAML → WorkflowSpec with schedule → validate."""

    def test_load_and_validate(self, tmp_path: Path):
        wf_file = tmp_path / "scheduled.yaml"
        wf_file.write_text(
            "name: test-scheduled\n"
            "schedule: '*/15 * * * *'\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    system_prompt: test\n"
            "    outputs: [result]\n"
        )
        spec = load_workflow(wf_file)
        assert spec.schedule == "*/15 * * * *"
        errors = validate_workflow(spec)
        assert not any("cron" in e.lower() for e in errors)

    def test_load_various_cron_expressions(self, tmp_path: Path):
        """Different valid cron expressions all load correctly."""
        crons = [
            "*/5 * * * *",      # every 5 min
            "0 * * * *",        # hourly
            "0 9 * * *",        # daily 9am
            "0 0 * * 0",        # weekly Sunday
            "30 2 * * 1-5",     # weekdays 2:30am
            "0 9-17 * * 1-5",   # business hours
            "0 0 1 * *",        # monthly
        ]
        for i, cron in enumerate(crons):
            wf_file = tmp_path / f"wf_{i}.yaml"
            wf_file.write_text(
                f"name: cron-test-{i}\n"
                f"schedule: '{cron}'\n"
                "nodes:\n"
                "  a:\n"
                "    agent: 'local://echo'\n"
                "    outputs: [r]\n"
            )
            spec = load_workflow(wf_file)
            assert spec.schedule == cron
            errors = validate_workflow(spec)
            assert not any("cron" in e.lower() for e in errors), f"Cron {cron!r} rejected"

    def test_schedule_none_when_absent(self, tmp_path: Path):
        """Workflow without schedule field → schedule is None."""
        wf_file = tmp_path / "no-sched.yaml"
        wf_file.write_text(
            "name: no-schedule\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [r]\n"
        )
        spec = load_workflow(wf_file)
        assert spec.schedule is None

    def test_scan_then_load_same_workflow(self, tmp_path: Path):
        """Scan discovers workflow, load_workflow reads same file — schedule matches."""
        wf_file = _write_wf(tmp_path / "wf.yaml", "roundtrip-wf", "*/10 * * * *")

        scanned = scan_directory(tmp_path)
        assert len(scanned) == 1

        spec = load_workflow(wf_file)
        assert spec.schedule == scanned[0].schedule
        assert spec.name == scanned[0].name

    def test_loaded_schedule_preserved_in_model_dump(self, tmp_path: Path):
        """Schedule survives load → model_dump → model_validate roundtrip."""
        wf_file = tmp_path / "sched.yaml"
        wf_file.write_text(
            "name: dump-test\n"
            "schedule: '0 6 * * *'\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [r]\n"
        )
        spec = load_workflow(wf_file)
        from binex.models.workflow import WorkflowSpec

        dumped = spec.model_dump()
        restored = WorkflowSpec.model_validate(dumped)
        assert restored.schedule == "0 6 * * *"


# ===========================================================================
# 5. Cron Validation Rejection
# ===========================================================================


class TestCronValidationRejection:
    """Integration: invalid cron in YAML → validation error."""

    def test_invalid_cron_rejected(self, tmp_path: Path):
        wf_file = tmp_path / "bad.yaml"
        wf_file.write_text(
            "name: bad-cron\n"
            "schedule: 'not valid'\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [result]\n"
        )
        spec = load_workflow(wf_file)
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1

    def test_empty_cron_rejected(self, tmp_path: Path):
        wf_file = tmp_path / "empty.yaml"
        wf_file.write_text(
            "name: empty-cron\n"
            "schedule: ''\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [r]\n"
        )
        spec = load_workflow(wf_file)
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1

    def test_out_of_range_cron_rejected(self, tmp_path: Path):
        wf_file = tmp_path / "range.yaml"
        wf_file.write_text(
            "name: range-cron\n"
            "schedule: '99 99 99 99 99'\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [r]\n"
        )
        spec = load_workflow(wf_file)
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1

    def test_too_few_fields_rejected(self, tmp_path: Path):
        wf_file = tmp_path / "few.yaml"
        wf_file.write_text(
            "name: few-fields\n"
            "schedule: '* *'\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [r]\n"
        )
        spec = load_workflow(wf_file)
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1

    def test_scan_skips_invalid_cron(self, tmp_path: Path):
        """scan_directory gracefully skips files with invalid cron."""
        _write_wf(tmp_path / "good.yaml", "good-wf", "*/5 * * * *")
        bad = tmp_path / "bad.yaml"
        bad.write_text(yaml.dump({
            "name": "bad-wf",
            "schedule": "not a cron",
            "nodes": {"a": {"agent": "local://echo", "outputs": ["r"]}},
        }))

        workflows = scan_directory(tmp_path)
        assert len(workflows) == 1
        assert workflows[0].name == "good-wf"

    def test_scheduled_workflow_model_rejects_invalid_cron(self):
        """ScheduledWorkflow pydantic model rejects invalid cron at creation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Invalid cron"):
            ScheduledWorkflow(
                name="bad",
                path="/tmp/bad.yaml",
                schedule="nope",
                next_run=datetime.now(UTC),
            )


# ===========================================================================
# 6. State Record Run Round-Trip
# ===========================================================================


class TestStateRecordRunRoundTrip:
    """Integration: record run → save → load → verify history."""

    def test_record_and_reload(self, tmp_path: Path):
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        record_run(state, "wf1", "run-001", "completed", 5.0, 0.02)
        record_run(state, "wf1", "run-002", "failed", 1.0)
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert len(loaded.history) == 2
        assert loaded.history[0].run_id == "run-001"
        assert loaded.history[0].cost == 0.02
        assert loaded.history[1].status == "failed"

    def test_mixed_records_roundtrip(self, tmp_path: Path):
        """Completed + failed + skipped records all persist correctly."""
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        record_run(state, "wf", "r1", "completed", 2.0, 0.01)
        record_run(state, "wf", "r2", "failed", 0.5)
        record_skip(state, "wf", "previous_still_running")
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert len(loaded.history) == 3
        statuses = [h.status for h in loaded.history]
        assert statuses == ["completed", "failed", "skipped"]

    def test_cost_none_preserved(self, tmp_path: Path):
        """Cost=None is preserved through save/load (not converted to 0)."""
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        record_run(state, "wf", "r1", "completed", 1.0)
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert loaded.history[0].cost is None

    def test_duration_none_on_skip(self, tmp_path: Path):
        """Skipped entry has no duration_s."""
        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        record_skip(state, "wf", "previous_still_running")
        save_state(state, state_path)

        loaded = load_state(state_path)
        assert loaded.history[0].duration_s is None
        assert loaded.history[0].run_id is None
