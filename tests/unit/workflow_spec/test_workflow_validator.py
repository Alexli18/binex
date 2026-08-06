"""Tests for workflow structural validator."""

from __future__ import annotations

from binex.models.workflow import WorkflowSpec
from binex.workflow_spec.validator import validate_workflow


def _make_spec(nodes: dict) -> WorkflowSpec:
    return WorkflowSpec(name="test", nodes=nodes)


def test_valid_simple_workflow(sample_workflow_dict: dict) -> None:
    spec = WorkflowSpec(**sample_workflow_dict)
    errors = validate_workflow(spec)
    assert errors == []


def test_valid_research_pipeline(sample_research_workflow_dict: dict) -> None:
    spec = WorkflowSpec(**sample_research_workflow_dict)
    errors = validate_workflow(spec)
    assert errors == []


def test_cycle_detection() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    errors = validate_workflow(spec)
    assert any("cycle" in e.lower() for e in errors)


def test_three_node_cycle() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["c"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
        "c": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
    })
    errors = validate_workflow(spec)
    assert any("cycle" in e.lower() for e in errors)


def test_missing_depends_on_ref() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["nonexistent"]},
    })
    errors = validate_workflow(spec)
    assert any("nonexistent" in e for e in errors)


def test_invalid_interpolation_node() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "inputs": {"x": "${ghost.output}"}},
    })
    errors = validate_workflow(spec)
    assert any("ghost" in e for e in errors)


def test_invalid_interpolation_output() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["result"]},
        "b": {
            "agent": "x",
            "outputs": ["o"],
            "depends_on": ["a"],
            "inputs": {"x": "${a.nonexistent}"},
        },
    })
    errors = validate_workflow(spec)
    assert any("nonexistent" in e for e in errors)


def test_no_entry_node() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "depends_on": ["b"]},
        "b": {"agent": "x", "outputs": ["o"], "depends_on": ["a"]},
    })
    errors = validate_workflow(spec)
    assert any("entry" in e.lower() or "cycle" in e.lower() for e in errors)


def test_valid_interpolation_with_user_var() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["o"], "inputs": {"q": "${user.query}"}},
    })
    errors = validate_workflow(spec)
    assert errors == []


def test_single_node_valid() -> None:
    spec = _make_spec({
        "a": {"agent": "x", "outputs": ["result"]},
    })
    errors = validate_workflow(spec)
    assert errors == []
