"""Tests for BackEdge model and NodeSpec.back_edge field."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from binex.models.workflow import BackEdge, NodeSpec, WorkflowSpec


class TestBackEdgeModel:
    def test_back_edge_defaults(self) -> None:
        be = BackEdge(target="generate", when="${review.decision} == rejected")
        assert be.target == "generate"
        assert be.when == "${review.decision} == rejected"
        assert be.max_iterations == 5

    def test_back_edge_custom_max_iterations(self) -> None:
        be = BackEdge(target="gen", when="${r.d} == rejected", max_iterations=3)
        assert be.max_iterations == 3

    def test_back_edge_max_iterations_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="max_iterations"):
            BackEdge(target="gen", when="${r.d} == rejected", max_iterations=0)

    def test_back_edge_requires_target(self) -> None:
        with pytest.raises(ValidationError):
            BackEdge(when="${r.d} == rejected")  # type: ignore[call-arg]

    def test_back_edge_requires_when(self) -> None:
        with pytest.raises(ValidationError):
            BackEdge(target="gen")  # type: ignore[call-arg]


class TestNodeSpecBackEdge:
    def test_node_spec_no_back_edge_by_default(self) -> None:
        ns = NodeSpec(agent="llm://test", outputs=["result"])
        assert ns.back_edge is None

    def test_node_spec_with_back_edge(self) -> None:
        ns = NodeSpec(
            agent="human://review",
            outputs=["result"],
            back_edge=BackEdge(
                target="generate",
                when="${review.decision} == rejected",
                max_iterations=3,
            ),
        )
        assert ns.back_edge is not None
        assert ns.back_edge.target == "generate"

    def test_node_spec_back_edge_from_dict(self) -> None:
        ns = NodeSpec(
            agent="human://review",
            outputs=["result"],
            back_edge={
                "target": "generate",
                "when": "${review.decision} == rejected",
            },
        )
        assert isinstance(ns.back_edge, BackEdge)
        assert ns.back_edge.max_iterations == 5
