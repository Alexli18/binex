"""Scheduler domain models — ScheduledWorkflow, HistoryEntry, SchedulerState."""

from __future__ import annotations

from datetime import UTC, datetime

from croniter import croniter
from pydantic import BaseModel, Field, field_validator


class ScheduledWorkflow(BaseModel):
    """A workflow registered for recurring scheduled execution."""

    name: str
    path: str
    schedule: str
    next_run: datetime

    @field_validator("schedule")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: {v!r}")
        return v

    def advance_next_run(self) -> None:
        """Recalculate next_run from the current time."""
        self.next_run = datetime.fromtimestamp(
            croniter(self.schedule, datetime.now(UTC)).get_next(),
            tz=UTC,
        )


class HistoryEntry(BaseModel):
    """A single event in the scheduler's execution log."""

    workflow: str
    timestamp: datetime
    run_id: str | None = None
    status: str
    reason: str | None = None
    duration_s: float | None = None
    cost: float | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"completed", "failed", "skipped"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got {v!r}")
        return v


HISTORY_MAX = 1000


class SchedulerState(BaseModel):
    """Aggregate root for scheduler persistence."""

    registered: list[str] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)

    def add_history(self, entry: HistoryEntry) -> None:
        """Append a history entry, pruning oldest if over capacity."""
        self.history.append(entry)
        if len(self.history) > HISTORY_MAX:
            self.history = self.history[-HISTORY_MAX:]


__all__ = ["HistoryEntry", "ScheduledWorkflow", "SchedulerState", "HISTORY_MAX"]
