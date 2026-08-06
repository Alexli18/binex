"""Tests for task lifecycle state machine."""

from __future__ import annotations

import pytest

from binex.models.task import TaskStatus
from binex.runtime.lifecycle import InvalidTransitionError, transition


def test_valid_transitions() -> None:
    assert transition(TaskStatus.REQUESTED, TaskStatus.ACCEPTED) == TaskStatus.ACCEPTED
    assert transition(TaskStatus.ACCEPTED, TaskStatus.RUNNING) == TaskStatus.RUNNING
    assert transition(TaskStatus.RUNNING, TaskStatus.COMPLETED) == TaskStatus.COMPLETED
    assert transition(TaskStatus.RUNNING, TaskStatus.FAILED) == TaskStatus.FAILED
    assert transition(TaskStatus.RUNNING, TaskStatus.CANCELLED) == TaskStatus.CANCELLED
    assert transition(TaskStatus.RUNNING, TaskStatus.TIMED_OUT) == TaskStatus.TIMED_OUT
    assert transition(TaskStatus.FAILED, TaskStatus.REQUESTED) == TaskStatus.REQUESTED


def test_invalid_transition_requested_to_running() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(TaskStatus.REQUESTED, TaskStatus.RUNNING)


def test_invalid_transition_completed_to_anything() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(TaskStatus.COMPLETED, TaskStatus.REQUESTED)


def test_invalid_transition_cancelled_to_anything() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(TaskStatus.CANCELLED, TaskStatus.RUNNING)


def test_error_message_contains_states() -> None:
    with pytest.raises(InvalidTransitionError, match="requested.*running"):
        transition(TaskStatus.REQUESTED, TaskStatus.RUNNING)
