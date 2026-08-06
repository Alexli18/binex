"""Unit tests for foreach pure helpers, DAG/scheduler mutation, validation (#77)."""

from __future__ import annotations

import pytest

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.foreach import (
    ForeachError,
    ForeachGroup,
    aggregator_node_id,
    build_aggregate_content,
    build_worker_spec,
    estimate_expansion_cost,
    item_identity,
    parse_items,
    worker_node_id,
)
from binex.workflow_spec.validator import validate_workflow

# --- parse_items ----------------------------------------------------------

def test_parse_items_list() -> None:
    assert parse_items([1, 2, 3]) == [1, 2, 3]


def test_parse_items_json_string() -> None:
    assert parse_items('[{"id": 1}]') == [{"id": 1}]


def test_parse_items_non_array_json_raises() -> None:
    with pytest.raises(ForeachError, match="not an array"):
        parse_items('{"a": 1}')


def test_parse_items_bad_json_raises() -> None:
    with pytest.raises(ForeachError, match="not valid JSON"):
        parse_items("not json")


def test_parse_items_wrong_type_raises() -> None:
    with pytest.raises(ForeachError, match="must be an array"):
        parse_items(42)


# --- item_identity --------------------------------------------------------

def test_identity_by_content_is_stable_and_order_independent() -> None:
    a = item_identity({"x": 1, "y": 2}, None, 0)
    b = item_identity({"y": 2, "x": 1}, None, 5)  # same content, different index
    assert a == b


def test_identity_content_differs() -> None:
    assert item_identity({"x": 1}, None, 0) != item_identity({"x": 2}, None, 0)


def test_identity_explicit_key() -> None:
    ident = item_identity({"id": "episode-42", "n": 7}, "$.id", 0)
    assert ident == "episode-42"


def test_identity_key_falls_back_to_hash_when_absent() -> None:
    # key path missing → content hash (12 hex chars)
    ident = item_identity({"n": 7}, "$.id", 0)
    assert len(ident) == 12


# --- spec building --------------------------------------------------------

def test_build_worker_spec_clones_template() -> None:
    fnode = NodeSpec(
        id="work", agent="llm://x", outputs=["out"], foreach="map",
        system_prompt="do it", cache=True,
    )
    w = build_worker_spec(fnode, "work::abc")
    assert w.id == "work::abc"
    assert w.agent == "llm://x"
    assert w.foreach is None
    assert w.depends_on == []
    assert w.cache is True


def test_estimate_cost_from_node_budget() -> None:
    fnode = NodeSpec(id="w", agent="llm://x", outputs=["o"], foreach="m", budget=0.5)
    assert estimate_expansion_cost(fnode, 4) == 2.0


def test_estimate_cost_none_without_budget() -> None:
    fnode = NodeSpec(id="w", agent="llm://x", outputs=["o"], foreach="m")
    assert estimate_expansion_cost(fnode, 4) is None


# --- aggregation ----------------------------------------------------------

def test_build_aggregate_content() -> None:
    group = ForeachGroup(
        foreach_id="w", mapper_id="m", aggregator_id="w::aggregate",
        worker_ids=["w::a", "w::b", "w::c"], on_item_failure="continue",
        outputs=["out"], failed=["w::b"],
    )

    class _A:
        def __init__(self, c: object) -> None:
            self.content = c

    outputs = {"w::a": [_A("ra")], "w::c": [_A("rc")]}  # b failed → no output
    content = build_aggregate_content(group, outputs)
    assert content["total"] == 3
    assert content["succeeded"] == 2
    assert content["failed"] == ["w::b"]
    assert content["results"] == ["ra", "rc"]


# --- DAG / scheduler mutation --------------------------------------------

def test_dag_add_node_and_rewire() -> None:
    spec = WorkflowSpec(nodes={
        "m": NodeSpec(id="m", agent="local://x", outputs=["o"]),
        "f": NodeSpec(id="f", agent="local://x", outputs=["o"], depends_on=["m"]),
        "sink": NodeSpec(id="sink", agent="local://x", outputs=["o"], depends_on=["f"]),
    }, name="t")
    dag = DAG.from_workflow(spec)

    dag.add_node("f::w0", set())
    dag.add_node("f::aggregate", {"f::w0"})
    assert "f::w0" in dag.nodes
    assert "f::aggregate" in dag.dependents("f::w0")

    # sink depended on f → rewire to aggregator
    dag.rewire_dependents("f", "f::aggregate")
    assert "sink" in dag.dependents("f::aggregate")
    assert "sink" not in dag.dependents("f")
    assert "f::aggregate" in dag.dependencies("sink")


def test_scheduler_add_node_ready_and_pending() -> None:
    spec = WorkflowSpec(nodes={
        "a": NodeSpec(id="a", agent="local://x", outputs=["o"]),
    }, name="t")
    dag = DAG.from_workflow(spec)
    sched = Scheduler(dag)

    dag.add_node("w", set())
    sched.add_node("w", 0)
    assert "w" in sched.ready_nodes()

    dag.add_node("agg", {"w"})
    sched.add_node("agg", 1)
    assert "agg" not in sched.ready_nodes()

    sched.mark_running("w")
    sched.mark_completed("w")  # satisfies agg
    assert "agg" in sched.ready_nodes()


def test_scheduler_satisfy_dependents_without_completion() -> None:
    spec = WorkflowSpec(nodes={
        "a": NodeSpec(id="a", agent="local://x", outputs=["o"]),
    }, name="t")
    dag = DAG.from_workflow(spec)
    sched = Scheduler(dag)
    dag.add_node("w", set())
    sched.add_node("w", 0)
    dag.add_node("agg", {"w"})
    sched.add_node("agg", 1)

    sched.mark_running("w")
    sched.mark_failed("w")
    assert "agg" not in sched.ready_nodes()  # failed does not satisfy
    sched.satisfy_dependents("w")            # continue-policy override
    assert "agg" in sched.ready_nodes()


# --- validation -----------------------------------------------------------

def test_validate_foreach_unknown_mapper() -> None:
    spec = WorkflowSpec(nodes={
        "w": NodeSpec(id="w", agent="llm://x", outputs=["o"], foreach="ghost"),
    }, name="t")
    errors = validate_workflow(spec)
    assert any("foreach references unknown node 'ghost'" in e for e in errors)


def test_validate_foreach_self_reference() -> None:
    spec = WorkflowSpec(nodes={
        "w": NodeSpec(id="w", agent="llm://x", outputs=["o"], foreach="w"),
    }, name="t")
    errors = validate_workflow(spec)
    assert any("cannot reference itself" in e for e in errors)


def test_foreach_auto_adds_mapper_dependency() -> None:
    spec = WorkflowSpec(nodes={
        "m": NodeSpec(id="m", agent="local://x", outputs=["o"]),
        "w": NodeSpec(id="w", agent="llm://x", outputs=["o"], foreach="m"),
    }, name="t")
    assert "m" in spec.nodes["w"].depends_on


def test_worker_and_aggregator_ids() -> None:
    assert worker_node_id("w", "abc") == "w::abc"
    assert aggregator_node_id("w") == "w::aggregate"
