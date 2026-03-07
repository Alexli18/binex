"""TaskNode, TaskStatus, and RetryPolicy domain models."""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(enum.StrEnum):
    """Lifecycle states for a task node."""

    REQUESTED = "requested"
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

    @classmethod
    def valid_transitions(cls) -> dict[TaskStatus, set[TaskStatus]]:
        return {
            cls.REQUESTED: {cls.ACCEPTED},
            cls.ACCEPTED: {cls.RUNNING},
            cls.RUNNING: {cls.COMPLETED, cls.FAILED, cls.CANCELLED, cls.TIMED_OUT},
            cls.FAILED: {cls.REQUESTED},
            cls.COMPLETED: set(),
            cls.CANCELLED: set(),
            cls.TIMED_OUT: set(),
        }


class RetryPolicy(BaseModel):
    """Retry configuration for a task node."""

    max_retries: int = 1
    backoff: Literal["fixed", "exponential"] = "exponential"


class TaskNode(BaseModel):
    """Runtime representation of a node during execution."""

    id: str
    run_id: str
    node_id: str
    agent: str
    skill: str | None = None
    status: TaskStatus = TaskStatus.REQUESTED
    input_artifact_refs: list[str] = Field(default_factory=list)
    output_artifact_refs: list[str] = Field(default_factory=list)
    attempt: int = 1
    retry_policy: RetryPolicy | None = None
    deadline_ms: int | None = None


__all__ = ["RetryPolicy", "TaskNode", "TaskStatus"]
