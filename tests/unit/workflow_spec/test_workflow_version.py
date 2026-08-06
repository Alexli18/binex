"""Tests for workflow version field."""

import pytest

from binex.models.workflow import NodeSpec, WorkflowSpec


def test_workflow_spec_default_version():
    """WorkflowSpec defaults to version 1."""
    spec = WorkflowSpec(
        name="test", nodes={"a": NodeSpec(agent="local://echo", outputs=["out"])}
    )
    assert spec.version == 1


def test_workflow_spec_explicit_version():
    """WorkflowSpec accepts explicit version."""
    spec = WorkflowSpec(
        name="test",
        version=2,
        nodes={"a": NodeSpec(agent="local://echo", outputs=["out"])},
    )
    assert spec.version == 2


def test_workflow_spec_version_must_be_positive():
    """version < 1 should fail validation."""
    with pytest.raises(ValueError):
        WorkflowSpec(
            name="test",
            version=0,
            nodes={"a": NodeSpec(agent="local://echo", outputs=["out"])},
        )
