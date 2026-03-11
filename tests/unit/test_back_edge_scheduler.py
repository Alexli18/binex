"""Tests for Scheduler back-edge re-execution support."""
from __future__ import annotations

import pytest

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.workflow import WorkflowSpec


def _make_scheduler(nodes_dict: dict) -> tuple[Scheduler, DAG]:
    spec = WorkflowSpec(name="test", nodes=nodes_dict)
    dag = DAG.from_workflow(spec)
    return Scheduler(dag), dag


class TestExecutionCount:
    def test_initial_count_is_zero(self) -> None:
        sched, _ = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        assert sched.get_execution_count("a") == 0

    def test_count_increments_on_mark_pending_again(self) -> None:
        sched, _ = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        sched.mark_pending_again("a")
        assert sched.get_execution_count("a") == 1

    def test_count_increments_each_reset(self) -> None:
        sched, _ = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        for _ in range(3):
            sched.mark_running("a")
            sched.mark_completed("a")
            sched.mark_pending_again("a")
        assert sched.get_execution_count("a") == 3


class TestMarkPendingAgain:
    def test_removes_from_completed(self) -> None:
        sched, _ = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        assert "a" in sched._completed
        sched.mark_pending_again("a")
        assert "a" not in sched._completed
        assert "a" not in sched._running
        assert "a" not in sched._failed

    def test_node_becomes_ready_again(self) -> None:
        sched, _ = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        assert sched.ready_nodes() == []
        sched.mark_pending_again("a")
        assert sched.ready_nodes() == ["a"]

    def test_is_complete_false_after_reset(self) -> None:
        sched, _ = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        assert sched.is_complete()
        sched.mark_pending_again("a")
        assert not sched.is_complete()


class TestResetChain:
    def test_resets_linear_chain(self) -> None:
        sched, dag = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
            "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
            "c": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        sched.mark_running("b")
        sched.mark_completed("b")
        sched.mark_running("c")
        sched.mark_completed("c")
        reset = sched.reset_chain("a", "c", dag)
        assert set(reset) == {"a", "b", "c"}
        assert sched.ready_nodes() == ["a"]

    def test_resets_partial_chain(self) -> None:
        sched, dag = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
            "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
            "c": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        sched.mark_running("b")
        sched.mark_completed("b")
        sched.mark_running("c")
        sched.mark_completed("c")
        # Reset from b to c only — a stays completed
        reset = sched.reset_chain("b", "c", dag)
        assert set(reset) == {"b", "c"}
        assert "a" in sched._completed
        assert sched.ready_nodes() == ["b"]

    def test_reset_single_node(self) -> None:
        sched, dag = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
        })
        sched.mark_running("a")
        sched.mark_completed("a")
        reset = sched.reset_chain("a", "a", dag)
        assert reset == ["a"]

    def test_reset_with_branch_outside_chain(self) -> None:
        """Nodes not on path from_node->to_node are NOT reset."""
        sched, dag = _make_scheduler({
            "a": {"agent": "x", "outputs": ["o"]},
            "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
            "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
            "d": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        })
        for n in ["a", "b", "c", "d"]:
            sched.mark_running(n)
            sched.mark_completed(n)
        # Reset a -> d path: a, b, d. Node c is NOT on path.
        reset = sched.reset_chain("a", "d", dag)
        assert "c" not in reset
        assert "a" in reset
        assert "b" in reset
        assert "d" in reset
