"""Tests for schedule field on WorkflowSpec and cron validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from binex.models.workflow import WorkflowSpec
from binex.scheduler.models import HistoryEntry, ScheduledWorkflow, SchedulerState
from binex.workflow_spec.validator import validate_workflow

# --- WorkflowSpec.schedule field ---


class TestWorkflowSpecSchedule:
    def test_schedule_default_none(self):
        spec = WorkflowSpec(name="test", nodes={})
        assert spec.schedule is None

    def test_schedule_valid_cron(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="*/5 * * * *")
        assert spec.schedule == "*/5 * * * *"

    def test_schedule_hourly(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="0 * * * *")
        assert spec.schedule == "0 * * * *"

    def test_schedule_daily(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="0 9 * * *")
        assert spec.schedule == "0 9 * * *"

    def test_schedule_preserves_string(self):
        cron = "30 2 * * 1-5"
        spec = WorkflowSpec(name="test", nodes={}, schedule=cron)
        assert spec.schedule == cron


# --- Cron validation in workflow validator ---


class TestCronValidation:
    def test_valid_cron_no_error(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="*/10 * * * *")
        errors = validate_workflow(spec)
        assert not any("cron" in e.lower() for e in errors)

    def test_invalid_cron_produces_error(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="bad cron")
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1
        assert "bad cron" in cron_errors[0]

    def test_no_schedule_no_cron_error(self):
        spec = WorkflowSpec(name="test", nodes={})
        errors = validate_workflow(spec)
        assert not any("cron" in e.lower() for e in errors)

    def test_invalid_cron_empty_string(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="")
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1

    def test_invalid_cron_out_of_range(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="99 99 99 99 99")
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1

    def test_valid_cron_with_ranges(self):
        spec = WorkflowSpec(name="test", nodes={}, schedule="0 9-17 * * 1-5")
        errors = validate_workflow(spec)
        assert not any("cron" in e.lower() for e in errors)


# --- ScheduledWorkflow model ---


class TestScheduledWorkflow:
    def test_create_valid(self):
        from datetime import UTC, datetime

        sw = ScheduledWorkflow(
            name="test",
            path="/tmp/test.yaml",
            schedule="*/5 * * * *",
            next_run=datetime.now(UTC),
        )
        assert sw.name == "test"
        assert sw.schedule == "*/5 * * * *"

    def test_invalid_cron_raises(self):
        from datetime import UTC, datetime

        with pytest.raises(ValidationError, match="Invalid cron"):
            ScheduledWorkflow(
                name="test",
                path="/tmp/test.yaml",
                schedule="not a cron",
                next_run=datetime.now(UTC),
            )

    def test_advance_next_run(self):
        from datetime import UTC, datetime

        sw = ScheduledWorkflow(
            name="test",
            path="/tmp/test.yaml",
            schedule="*/5 * * * *",
            next_run=datetime(2020, 1, 1, tzinfo=UTC),
        )
        old = sw.next_run
        sw.advance_next_run()
        assert sw.next_run > old


# --- HistoryEntry model ---


class TestHistoryEntry:
    def test_valid_completed(self):
        from datetime import UTC, datetime

        entry = HistoryEntry(
            workflow="test",
            timestamp=datetime.now(UTC),
            run_id="run-1",
            status="completed",
            duration_s=1.5,
            cost=0.01,
        )
        assert entry.status == "completed"

    def test_valid_skipped(self):
        from datetime import UTC, datetime

        entry = HistoryEntry(
            workflow="test",
            timestamp=datetime.now(UTC),
            status="skipped",
            reason="previous_still_running",
        )
        assert entry.run_id is None

    def test_invalid_status_raises(self):
        from datetime import UTC, datetime

        with pytest.raises(ValidationError, match="status must be one of"):
            HistoryEntry(
                workflow="test",
                timestamp=datetime.now(UTC),
                status="unknown",
            )


# --- SchedulerState model ---


class TestSchedulerState:
    def test_default_empty(self):
        state = SchedulerState()
        assert state.registered == []
        assert state.history == []

    def test_add_history(self):
        from datetime import UTC, datetime

        state = SchedulerState()
        entry = HistoryEntry(
            workflow="test",
            timestamp=datetime.now(UTC),
            status="completed",
            run_id="run-1",
        )
        state.add_history(entry)
        assert len(state.history) == 1

    def test_history_cap(self):
        from datetime import UTC, datetime

        state = SchedulerState()
        for i in range(1100):
            state.add_history(
                HistoryEntry(
                    workflow="test",
                    timestamp=datetime.now(UTC),
                    status="completed",
                    run_id=f"run-{i}",
                )
            )
        assert len(state.history) == 1000


# --- US1 Acceptance Scenario Tests ---


class TestUS1AcceptanceScenarios:
    """Acceptance scenarios from spec: US1 — Define a Workflow Schedule in YAML."""

    def test_valid_cron_parsed_and_accessible(self):
        """AS1: schedule: '0 9 * * *' → field preserved and accessible."""
        spec = WorkflowSpec(name="daily-report", nodes={}, schedule="0 9 * * *")
        assert spec.schedule == "0 9 * * *"

    def test_invalid_cron_rejected_with_error(self):
        """AS2: schedule: 'not-a-cron' → validation error."""
        spec = WorkflowSpec(name="bad", nodes={}, schedule="not-a-cron")
        errors = validate_workflow(spec)
        cron_errors = [e for e in errors if "cron" in e.lower()]
        assert len(cron_errors) == 1
        assert "not-a-cron" in cron_errors[0]

    def test_missing_schedule_no_error(self):
        """AS3: no schedule → defaults to None, no validation error."""
        spec = WorkflowSpec(name="no-schedule", nodes={})
        assert spec.schedule is None
        errors = validate_workflow(spec)
        assert not any("cron" in e.lower() or "schedule" in e.lower() for e in errors)

    def test_schedule_preserved_in_model_dump(self):
        """Schedule field preserved through serialization round-trip."""
        spec = WorkflowSpec(name="test", nodes={}, schedule="*/30 * * * *")
        dumped = spec.model_dump()
        assert dumped["schedule"] == "*/30 * * * *"

        restored = WorkflowSpec.model_validate(dumped)
        assert restored.schedule == "*/30 * * * *"

    def test_schedule_loads_from_yaml(self, tmp_path):
        """Verify schedule field loads correctly via load_workflow()."""
        from binex.workflow_spec.loader import load_workflow

        wf_file = tmp_path / "sched.yaml"
        wf_file.write_text(
            "name: yaml-test\n"
            "schedule: '0 9 * * *'\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [result]\n"
        )
        spec = load_workflow(wf_file)
        assert spec.schedule == "0 9 * * *"
        assert spec.name == "yaml-test"

    def test_schedule_missing_in_yaml_is_none(self, tmp_path):
        """Verify missing schedule → None via load_workflow()."""
        from binex.workflow_spec.loader import load_workflow

        wf_file = tmp_path / "no-sched.yaml"
        wf_file.write_text(
            "name: no-sched\n"
            "nodes:\n"
            "  a:\n"
            "    agent: 'local://echo'\n"
            "    outputs: [result]\n"
        )
        spec = load_workflow(wf_file)
        assert spec.schedule is None
