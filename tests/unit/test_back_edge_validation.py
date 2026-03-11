"""Tests for back_edge validation during workflow loading."""
from __future__ import annotations

import pytest

from binex.workflow_spec.loader import load_workflow_from_string


VALID_YAML = """
name: test
nodes:
  generate:
    agent: llm://test
    outputs: [result]
  review:
    agent: human://review
    outputs: [result]
    depends_on: [generate]
    back_edge:
      target: generate
      when: "${review.decision} == rejected"
      max_iterations: 3
"""

class TestBackEdgeValidation:
    def test_valid_back_edge_loads(self) -> None:
        spec = load_workflow_from_string(VALID_YAML)
        assert spec.nodes["review"].back_edge is not None
        assert spec.nodes["review"].back_edge.target == "generate"

    def test_back_edge_target_not_found(self) -> None:
        yaml = """
name: test
nodes:
  generate:
    agent: llm://test
    outputs: [result]
  review:
    agent: human://review
    outputs: [result]
    depends_on: [generate]
    back_edge:
      target: nonexistent
      when: "${review.decision} == rejected"
"""
        with pytest.raises(ValueError, match="nonexistent.*not found"):
            load_workflow_from_string(yaml)

    def test_back_edge_target_not_upstream(self) -> None:
        yaml = """
name: test
nodes:
  generate:
    agent: llm://test
    outputs: [result]
  review:
    agent: human://review
    outputs: [result]
    depends_on: [generate]
    back_edge:
      target: output
      when: "${review.decision} == rejected"
  output:
    agent: llm://test
    outputs: [result]
    depends_on: [review]
"""
        with pytest.raises(ValueError, match="output.*not upstream"):
            load_workflow_from_string(yaml)

    def test_back_edge_invalid_when_syntax(self) -> None:
        yaml = """
name: test
nodes:
  generate:
    agent: llm://test
    outputs: [result]
  review:
    agent: human://review
    outputs: [result]
    depends_on: [generate]
    back_edge:
      target: generate
      when: "bad syntax here"
"""
        with pytest.raises(ValueError, match="invalid when condition syntax"):
            load_workflow_from_string(yaml)

    def test_no_back_edge_works_as_before(self) -> None:
        yaml = """
name: test
nodes:
  a:
    agent: llm://test
    outputs: [result]
  b:
    agent: llm://test
    outputs: [result]
    depends_on: [a]
"""
        spec = load_workflow_from_string(yaml)
        assert spec.nodes["a"].back_edge is None
        assert spec.nodes["b"].back_edge is None
