"""Scheduler state persistence — load/save JSON, record runs and skips."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from binex.scheduler.models import HistoryEntry, SchedulerState

DEFAULT_STATE_PATH = Path(".binex/scheduler.json")


def load_state(path: Path = DEFAULT_STATE_PATH) -> SchedulerState:
    """Load scheduler state from JSON file. Returns empty state if missing."""
    if not path.exists():
        return SchedulerState()
    data = json.loads(path.read_text(encoding="utf-8"))
    return SchedulerState.model_validate(data)


def save_state(state: SchedulerState, path: Path = DEFAULT_STATE_PATH) -> None:
    """Persist scheduler state to JSON file (atomic write via tempfile + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(state.model_dump(mode="json"), indent=2, default=str)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    closed = False
    try:
        os.write(fd, data.encode("utf-8"))
        os.close(fd)
        closed = True
        os.replace(tmp, path)
    except BaseException:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def record_run(
    state: SchedulerState,
    workflow: str,
    run_id: str,
    status: str,
    duration_s: float | None = None,
    cost: float | None = None,
) -> None:
    """Record a workflow execution in history."""
    entry = HistoryEntry(
        workflow=workflow,
        timestamp=datetime.now(UTC),
        run_id=run_id,
        status=status,
        duration_s=duration_s,
        cost=cost,
    )
    state.add_history(entry)


def record_skip(
    state: SchedulerState,
    workflow: str,
    reason: str,
) -> None:
    """Record a skipped execution in history."""
    entry = HistoryEntry(
        workflow=workflow,
        timestamp=datetime.now(UTC),
        status="skipped",
        reason=reason,
    )
    state.add_history(entry)


__all__ = ["DEFAULT_STATE_PATH", "load_state", "save_state", "record_run", "record_skip"]
