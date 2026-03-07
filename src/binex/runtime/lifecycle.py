"""Task lifecycle state machine — enforces valid status transitions."""

from __future__ import annotations

from binex.models.task import TaskStatus


class InvalidTransitionError(Exception):
    """Raised when an invalid task status transition is attempted."""


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    """Validate and perform a task status transition."""
    valid = TaskStatus.valid_transitions()
    if target not in valid.get(current, set()):
        raise InvalidTransitionError(
            f"Invalid transition from '{current}' to '{target}'"
        )
    return target
