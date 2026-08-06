"""Tests for scheduler state persistence — load/save, record_run, record_skip."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from binex.scheduler.models import HISTORY_MAX, HistoryEntry, SchedulerState
from binex.scheduler.state import (
    load_state,
    record_run,
    record_skip,
    save_state,
)


class TestLoadState:
    def test_load_missing_file_returns_empty(self, tmp_path: Path):
        state = load_state(tmp_path / "nonexistent.json")
        assert state.registered == []
        assert state.history == []

    def test_load_existing_file(self, tmp_path: Path):
        path = tmp_path / "scheduler.json"
        path.write_text('{"registered": ["/tmp/a.yaml"], "history": []}')
        state = load_state(path)
        assert state.registered == ["/tmp/a.yaml"]


class TestSaveState:
    def test_save_creates_file(self, tmp_path: Path):
        path = tmp_path / "sub" / "scheduler.json"
        state = SchedulerState(registered=["/tmp/test.yaml"])
        save_state(state, path)
        assert path.exists()

    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "scheduler.json"
        state = SchedulerState(registered=["/a.yaml", "/b.yaml"])
        record_run(state, "wf1", "run-1", "completed", 2.5, 0.05)
        record_skip(state, "wf2", "previous_still_running")
        save_state(state, path)

        loaded = load_state(path)
        assert loaded.registered == ["/a.yaml", "/b.yaml"]
        assert len(loaded.history) == 2
        assert loaded.history[0].workflow == "wf1"
        assert loaded.history[0].status == "completed"
        assert loaded.history[0].run_id == "run-1"
        assert loaded.history[0].duration_s == 2.5
        assert loaded.history[0].cost == 0.05
        assert loaded.history[1].workflow == "wf2"
        assert loaded.history[1].status == "skipped"
        assert loaded.history[1].reason == "previous_still_running"


class TestRecordRun:
    def test_record_completed(self):
        state = SchedulerState()
        record_run(state, "test-wf", "run-1", "completed", 1.0, 0.01)
        assert len(state.history) == 1
        assert state.history[0].run_id == "run-1"
        assert state.history[0].status == "completed"

    def test_record_failed(self):
        state = SchedulerState()
        record_run(state, "test-wf", "run-2", "failed", 0.5)
        assert state.history[0].status == "failed"
        assert state.history[0].cost is None

    def test_timestamp_is_set(self):
        state = SchedulerState()
        before = datetime.now(UTC)
        record_run(state, "wf", "run-1", "completed")
        after = datetime.now(UTC)
        ts = state.history[0].timestamp
        assert before <= ts <= after


class TestRecordSkip:
    def test_record_skip(self):
        state = SchedulerState()
        record_skip(state, "test-wf", "previous_still_running")
        assert len(state.history) == 1
        assert state.history[0].status == "skipped"
        assert state.history[0].reason == "previous_still_running"
        assert state.history[0].run_id is None

    def test_skip_has_no_duration(self):
        state = SchedulerState()
        record_skip(state, "wf", "overlap")
        assert state.history[0].duration_s is None


class TestHistoryCap:
    """add_history() caps at HISTORY_MAX — no separate _trim_history needed."""

    def test_under_cap_no_pruning(self):
        state = SchedulerState()
        for i in range(10):
            state.add_history(HistoryEntry(
                workflow="wf", timestamp=datetime.now(UTC),
                status="completed", run_id=f"r-{i}",
            ))
        assert len(state.history) == 10

    def test_over_cap_prunes_oldest(self):
        state = SchedulerState()
        for i in range(HISTORY_MAX + 50):
            state.add_history(HistoryEntry(
                workflow="wf", timestamp=datetime.now(UTC),
                status="completed", run_id=f"r-{i}",
            ))
        assert len(state.history) == HISTORY_MAX
        assert state.history[-1].run_id == f"r-{HISTORY_MAX + 49}"

    def test_preserves_newest(self):
        state = SchedulerState()
        for i in range(HISTORY_MAX + 5):
            state.add_history(HistoryEntry(
                workflow="wf", timestamp=datetime.now(UTC),
                status="completed", run_id=f"r-{i}",
            ))
        assert state.history[0].run_id == "r-5"
