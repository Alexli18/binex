"""Tests for updated HumanApprovalAdapter with feedback collection."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from binex.adapters.human import HumanApprovalAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


def _make_task(node_id: str = "review", run_id: str = "run_1") -> TaskNode:
    return TaskNode(
        id=f"{run_id}_{node_id}",
        run_id=run_id,
        node_id=node_id,
        agent="human://review",
        system_prompt=None,
        tools=[],
        inputs={},
    )


def _make_artifact(content: str = "draft text", art_type: str = "llm_response") -> Artifact:
    return Artifact(
        id="art_test1",
        run_id="run_1",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="generate"),
    )


class TestApproveFlow:
    @pytest.mark.asyncio
    async def test_approve_returns_decision_artifact(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        arts = [_make_artifact()]
        with patch("binex.adapters.human.click.prompt", return_value="a"), \
             patch("binex.adapters.human.click.echo"):
            result = await adapter.execute(task, arts, "trace_1")
        decisions = [a for a in result.artifacts if a.type == "decision"]
        assert len(decisions) == 1
        assert decisions[0].content == "approved"

    @pytest.mark.asyncio
    async def test_approve_has_no_feedback_artifact(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        arts = [_make_artifact()]
        with patch("binex.adapters.human.click.prompt", return_value="a"), \
             patch("binex.adapters.human.click.echo"):
            result = await adapter.execute(task, arts, "trace_1")
        feedbacks = [a for a in result.artifacts if a.type == "feedback"]
        assert len(feedbacks) == 0

    @pytest.mark.asyncio
    async def test_approve_returns_cost_record(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        arts = [_make_artifact()]
        with patch("binex.adapters.human.click.prompt", return_value="a"), \
             patch("binex.adapters.human.click.echo"):
            result = await adapter.execute(task, arts, "trace_1")
        assert result.cost is not None
        assert result.cost.cost == 0.0


class TestRejectFlow:
    @pytest.mark.asyncio
    async def test_reject_returns_decision_and_feedback(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        arts = [_make_artifact()]
        with patch("binex.adapters.human.click.prompt", side_effect=["r", "fix the intro"]), \
             patch("binex.adapters.human.click.echo"):
            result = await adapter.execute(task, arts, "trace_1")
        decisions = [a for a in result.artifacts if a.type == "decision"]
        feedbacks = [a for a in result.artifacts if a.type == "feedback"]
        assert len(decisions) == 1
        assert decisions[0].content == "rejected"
        assert len(feedbacks) == 1
        assert feedbacks[0].content == "fix the intro"

    @pytest.mark.asyncio
    async def test_reject_multiline_feedback(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        arts = [_make_artifact()]
        with patch("binex.adapters.human.click.prompt", side_effect=["r", "m"]), \
             patch("binex.adapters.human.click.echo"), \
             patch("builtins.input", side_effect=["line one", "line two", ""]):
            result = await adapter.execute(task, arts, "trace_1")
        feedbacks = [a for a in result.artifacts if a.type == "feedback"]
        assert len(feedbacks) == 1
        assert "line one" in feedbacks[0].content
        assert "line two" in feedbacks[0].content

    @pytest.mark.asyncio
    async def test_feedback_lineage_derived_from_inputs(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        arts = [_make_artifact()]
        with patch("binex.adapters.human.click.prompt", side_effect=["r", "notes"]), \
             patch("binex.adapters.human.click.echo"):
            result = await adapter.execute(task, arts, "trace_1")
        feedbacks = [a for a in result.artifacts if a.type == "feedback"]
        assert feedbacks[0].lineage.produced_by == "review"
        assert "art_test1" in feedbacks[0].lineage.derived_from
