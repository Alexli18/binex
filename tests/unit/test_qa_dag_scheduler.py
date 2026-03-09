"""QA tests for DAG and Scheduler edge cases (P0)."""

from __future__ import annotations

import pytest

from binex.graph.dag import CycleError, DAG
from binex.graph.scheduler import Scheduler
from binex.models.workflow import WorkflowSpec


def _make_spec(nodes: dict) -> WorkflowSpec:
    return WorkflowSpec(name="test", nodes=nodes)


def _make_scheduler(nodes: dict) -> Scheduler:
    spec = _make_spec(nodes)
    dag = DAG.from_workflow(spec)
    return Scheduler(dag)


# ---------------------------------------------------------------------------
# TC-DAG-001: Self-reference detected as cycle
# ---------------------------------------------------------------------------


def test_self_reference_detected_as_cycle() -> None:
    """A node that depends on itself must be rejected as a cycle."""
    # Arrange
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })

    # Act / Assert
    with pytest.raises(CycleError, match="cycle"):
        DAG.from_workflow(spec)


# ---------------------------------------------------------------------------
# TC-DAG-003: Diamond dependency — D waits for both B and C
# ---------------------------------------------------------------------------


def test_diamond_dependency_d_waits_for_both_parents() -> None:
    """In A->B, A->C, B->D, C->D, node D must not become ready until both B and C complete."""
    # Arrange
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["b", "c"]},
    })

    # Act — complete A, then only B
    sched.mark_completed("a")
    sched.mark_completed("b")

    # Assert — D must NOT be ready yet (C still pending)
    assert "d" not in sched.ready_nodes()

    # Act — complete C
    sched.mark_completed("c")

    # Assert — now D is ready
    assert sched.ready_nodes() == ["d"]


# ---------------------------------------------------------------------------
# TC-DAG-006: Non-existent dependency reference
# ---------------------------------------------------------------------------


def test_non_existent_dependency_raises_value_error() -> None:
    """A node referencing a dependency that does not exist must raise ValueError."""
    # Arrange
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["ghost"]},
    })

    # Act / Assert
    with pytest.raises(ValueError, match="unknown node"):
        DAG.from_workflow(spec)


# ---------------------------------------------------------------------------
# Scheduler edge case: mark_running on non-existent node
# ---------------------------------------------------------------------------


def test_mark_running_non_existent_node_does_not_crash() -> None:
    """Calling mark_running with a node ID not in the DAG should not crash."""
    # Arrange
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
    })

    # Act / Assert — no exception raised
    sched.mark_running("does_not_exist")


# ---------------------------------------------------------------------------
# Scheduler edge case: mark_completed on node never marked running
# ---------------------------------------------------------------------------


def test_mark_completed_without_prior_mark_running() -> None:
    """Completing a node that was never marked running should still work."""
    # Arrange
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })

    # Act — skip mark_running, go straight to completed
    sched.mark_completed("a")

    # Assert — dependent is now unlocked
    assert sched.ready_nodes() == ["b"]
    assert "a" not in sched.ready_nodes()


# ---------------------------------------------------------------------------
# Scheduler edge case: mark_completed twice (idempotent)
# ---------------------------------------------------------------------------


def test_mark_completed_twice_is_idempotent() -> None:
    """Calling mark_completed twice on the same node should not cause errors or side-effects."""
    # Arrange
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })

    # Act
    sched.mark_completed("a")
    sched.mark_completed("a")  # second call

    # Assert — b is ready, a does not reappear, workflow state is consistent
    assert sched.ready_nodes() == ["b"]
    assert not sched.is_complete()

    sched.mark_completed("b")
    assert sched.is_complete()


# ---------------------------------------------------------------------------
# Scheduler edge case: mark_failed blocks entire downstream chain (3+ levels)
# ---------------------------------------------------------------------------


def test_mark_failed_blocks_entire_downstream_chain() -> None:
    """Failing a node must block all transitive dependents, not just direct children."""
    # Arrange — linear chain: a -> b -> c -> d
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["c"]},
    })

    # Act
    sched.mark_failed("a")

    # Assert — no downstream node can ever become ready
    assert sched.ready_nodes() == []
    assert not sched.is_complete()
    assert sched.is_blocked()


def test_mark_failed_blocks_deep_diamond() -> None:
    """Failing one branch of a diamond blocks the join node and everything after it."""
    # Arrange — a -> {b, c} -> d -> e
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["b", "c"]},
        "e": {"agent": "x", "outputs": ["o"], "depends_on": ["d"]},
    })

    # Act — complete a, then fail b (c can still run)
    sched.mark_completed("a")
    sched.mark_failed("b")
    sched.mark_completed("c")

    # Assert — d needs both b and c; b failed so d (and e) can never run
    assert sched.ready_nodes() == []
    assert sched.is_blocked()


# ---------------------------------------------------------------------------
# Scheduler edge case: is_blocked returns True when failed node blocks work
# ---------------------------------------------------------------------------


def test_is_blocked_true_when_failure_blocks_remaining() -> None:
    """is_blocked must be True when a failed node prevents all remaining nodes from running."""
    # Arrange
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })

    # Act
    sched.mark_failed("a")

    # Assert
    assert sched.is_blocked() is True
    assert sched.is_complete() is False


def test_is_blocked_false_when_work_remains_possible() -> None:
    """is_blocked must be False when there are still runnable nodes despite a failure elsewhere."""
    # Arrange — two independent chains: a->b and c->d; fail a, c is still runnable
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["c"]},
    })

    # Act
    sched.mark_failed("a")

    # Assert — c is still ready, so we are not fully blocked
    assert sched.is_blocked() is False
    assert sched.ready_nodes() == ["c"]
