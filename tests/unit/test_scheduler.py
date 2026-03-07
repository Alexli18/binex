"""Tests for DAG scheduler."""

from __future__ import annotations

import pytest

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.workflow import WorkflowSpec


def _make_spec(nodes: dict) -> WorkflowSpec:
    return WorkflowSpec(name="test", nodes=nodes)


def _make_scheduler(nodes: dict) -> Scheduler:
    spec = _make_spec(nodes)
    dag = DAG.from_workflow(spec)
    return Scheduler(dag)


def test_initial_ready_nodes() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    assert sched.ready_nodes() == ["a"]


def test_mark_completed_unlocks_dependents() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    assert sched.ready_nodes() == ["a"]
    sched.mark_completed("a")
    assert sched.ready_nodes() == ["b"]


def test_parallel_nodes_ready() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    sched.mark_completed("a")
    ready = sched.ready_nodes()
    assert set(ready) == {"b", "c"}


def test_diamond_scheduling() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["b", "c"]},
    })
    assert sched.ready_nodes() == ["a"]
    sched.mark_completed("a")
    ready = sched.ready_nodes()
    assert set(ready) == {"b", "c"}

    sched.mark_running("b")
    sched.mark_running("c")
    sched.mark_completed("b")
    assert sched.ready_nodes() == []  # d still waiting on c

    sched.mark_completed("c")
    assert sched.ready_nodes() == ["d"]


def test_mark_failed() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    sched.mark_failed("a")
    assert sched.ready_nodes() == []
    assert sched.is_blocked()


def test_is_complete() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    assert not sched.is_complete()
    sched.mark_completed("a")
    assert not sched.is_complete()
    sched.mark_completed("b")
    assert sched.is_complete()


def test_research_pipeline_scheduling(sample_research_workflow_dict: dict) -> None:
    spec = WorkflowSpec(**sample_research_workflow_dict)
    dag = DAG.from_workflow(spec)
    sched = Scheduler(dag)

    assert sched.ready_nodes() == ["planner"]
    sched.mark_completed("planner")

    ready = sched.ready_nodes()
    assert set(ready) == {"researcher_1", "researcher_2"}
    sched.mark_completed("researcher_1")
    sched.mark_completed("researcher_2")

    assert sched.ready_nodes() == ["validator"]
    sched.mark_completed("validator")

    assert sched.ready_nodes() == ["summarizer"]
    sched.mark_completed("summarizer")
    assert sched.is_complete()


def test_mark_running() -> None:
    sched = _make_scheduler({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"]},
    })
    ready = sched.ready_nodes()
    assert set(ready) == {"a", "b"}
    sched.mark_running("a")
    # a is running, shouldn't appear in ready
    assert sched.ready_nodes() == ["b"]
