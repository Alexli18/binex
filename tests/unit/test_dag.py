"""Tests for DAG construction and cycle detection."""

from __future__ import annotations

import pytest

from binex.graph.dag import CycleError, DAG
from binex.models.workflow import WorkflowSpec


def _make_spec(nodes: dict) -> WorkflowSpec:
    return WorkflowSpec(name="test", nodes=nodes)


def test_build_simple_dag() -> None:
    spec = _make_spec({
        "producer": {"agent": "x", "outputs": ["result"]},
        "consumer": {"agent": "x", "outputs": ["final"], "depends_on": ["producer"]},
    })
    dag = DAG.from_workflow(spec)
    assert set(dag.nodes) == {"producer", "consumer"}


def test_entry_nodes() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    dag = DAG.from_workflow(spec)
    assert dag.entry_nodes() == ["a"]


def test_dependencies() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    dag = DAG.from_workflow(spec)
    assert dag.dependencies("b") == {"a"}
    assert dag.dependencies("a") == set()


def test_dependents() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    dag = DAG.from_workflow(spec)
    assert dag.dependents("a") == {"b"}
    assert dag.dependents("b") == set()


def test_topological_order_simple() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    dag = DAG.from_workflow(spec)
    order = dag.topological_order()
    assert order.index("a") < order.index("b")


def test_topological_order_diamond() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["b", "c"]},
    })
    dag = DAG.from_workflow(spec)
    order = dag.topological_order()
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_topological_order_research_pipeline(sample_research_workflow_dict: dict) -> None:
    spec = WorkflowSpec(**sample_research_workflow_dict)
    dag = DAG.from_workflow(spec)
    order = dag.topological_order()
    assert order.index("planner") < order.index("researcher_1")
    assert order.index("planner") < order.index("researcher_2")
    assert order.index("researcher_1") < order.index("validator")
    assert order.index("researcher_2") < order.index("validator")
    assert order.index("validator") < order.index("summarizer")


def test_cycle_detection() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    with pytest.raises(CycleError, match="cycle"):
        DAG.from_workflow(spec)


def test_three_node_cycle() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["c"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
    })
    with pytest.raises(CycleError):
        DAG.from_workflow(spec)


def test_single_node() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
    })
    dag = DAG.from_workflow(spec)
    assert dag.nodes == {"a"}
    assert dag.entry_nodes() == ["a"]
    assert dag.topological_order() == ["a"]


def test_linear_chain() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["c"]},
    })
    dag = DAG.from_workflow(spec)
    assert dag.topological_order() == ["a", "b", "c", "d"]


def test_entry_nodes_diamond() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "d": {"agent": "x", "outputs": ["o"], "depends_on": ["b", "c"]},
    })
    dag = DAG.from_workflow(spec)
    assert dag.entry_nodes() == ["a"]
