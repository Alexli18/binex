"""Tests for HumanApprovalAdapter and HumanInputAdapter."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from binex.adapters.human import HumanApprovalAdapter, HumanInputAdapter
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


def _make_task(run_id: str = "run_1", node_id: str = "review") -> TaskNode:
    return TaskNode(
        id="task_1",
        run_id=run_id,
        node_id=node_id,
        agent="human://approve",
    )


def _make_artifact(art_id: str = "art_input1", run_id: str = "run_1") -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type="text",
        content="Some content to review",
        lineage=Lineage(produced_by="prev_node"),
    )


class TestHumanApprovalAdapter:
    """Tests for the HumanApprovalAdapter."""

    def test_human_adapter_approve(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        inputs = [_make_artifact()]

        with patch("binex.adapters.human.click.prompt", return_value="y"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, inputs, "trace_1"))

        arts = result.artifacts
        assert len(arts) == 1
        assert arts[0].content == "approved"

    def test_human_adapter_reject(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        inputs = [_make_artifact()]

        with patch("binex.adapters.human.click.prompt", return_value="n"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, inputs, "trace_1"))

        arts = result.artifacts
        assert len(arts) == 1
        assert arts[0].content == "rejected"

    def test_human_adapter_artifact_type(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        inputs = [_make_artifact()]

        with patch("binex.adapters.human.click.prompt", return_value="y"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, inputs, "trace_1"))

        assert result.artifacts[0].type == "decision"

    def test_human_adapter_lineage(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task(node_id="review_step")
        art1 = _make_artifact(art_id="art_a")
        art2 = _make_artifact(art_id="art_b")

        with patch("binex.adapters.human.click.prompt", return_value="y"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, [art1, art2], "trace_1"))

        assert result.artifacts[0].lineage.produced_by == "review_step"
        assert result.artifacts[0].lineage.derived_from == ["art_a", "art_b"]

    def test_human_adapter_health(self) -> None:
        adapter = HumanApprovalAdapter()
        health = asyncio.run(adapter.health())
        assert health is AgentHealth.ALIVE

    def test_human_adapter_cancel(self) -> None:
        adapter = HumanApprovalAdapter()
        # Should not raise
        asyncio.run(adapter.cancel("task_123"))

    def test_human_adapter_displays_inputs(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        art = _make_artifact()

        with patch("binex.adapters.human.click.prompt", return_value="y") as mock_prompt, \
             patch("binex.adapters.human.click.echo") as mock_echo:
            asyncio.run(adapter.execute(task, [art], "trace_1"))

        # Verify that click.echo was called with err=True to display input artifacts
        assert mock_echo.call_count >= 1
        # At least one call should include artifact info on stderr
        stderr_calls = [c for c in mock_echo.call_args_list if c.kwargs.get("err") is True]
        assert len(stderr_calls) >= 1

    def test_human_adapter_artifact_run_id(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task(run_id="run_xyz")
        inputs = [_make_artifact(run_id="run_xyz")]

        with patch("binex.adapters.human.click.prompt", return_value="y"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, inputs, "trace_1"))

        assert result.artifacts[0].run_id == "run_xyz"

    def test_human_adapter_artifact_id_format(self) -> None:
        adapter = HumanApprovalAdapter()
        task = _make_task()
        inputs = [_make_artifact()]

        with patch("binex.adapters.human.click.prompt", return_value="y"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, inputs, "trace_1"))

        assert result.artifacts[0].id.startswith("art_")
        assert len(result.artifacts[0].id) == 16  # "art_" + 12 hex chars


class TestHumanInputAdapter:
    """Tests for the HumanInputAdapter (human://input)."""

    def _make_input_task(
        self, node_id: str = "user_input", system_prompt: str = "Enter topic",
    ) -> TaskNode:
        return TaskNode(
            id="task_2",
            run_id="run_1",
            node_id=node_id,
            agent="human://input",
            system_prompt=system_prompt,
        )

    def test_input_returns_user_text(self) -> None:
        adapter = HumanInputAdapter()
        task = self._make_input_task()

        with patch("binex.adapters.human.click.prompt", return_value="AI agents"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, [], "trace_1"))

        arts = result.artifacts
        assert len(arts) == 1
        assert arts[0].content == "AI agents"

    def test_input_artifact_type_is_human_input(self) -> None:
        adapter = HumanInputAdapter()
        task = self._make_input_task()

        with patch("binex.adapters.human.click.prompt", return_value="test"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, [], "trace_1"))

        assert result.artifacts[0].type == "human_input"

    def test_input_uses_system_prompt_as_prompt(self) -> None:
        adapter = HumanInputAdapter()
        task = self._make_input_task(system_prompt="What topic to research?")

        with patch("binex.adapters.human.click.prompt", return_value="x") as mock, \
             patch("binex.adapters.human.click.echo"):
            asyncio.run(adapter.execute(task, [], "trace_1"))

        mock.assert_called_once_with("What topic to research?")

    def test_input_shows_upstream_context(self) -> None:
        adapter = HumanInputAdapter()
        task = self._make_input_task()
        art = _make_artifact()

        with patch("binex.adapters.human.click.prompt", return_value="ok"), \
             patch("binex.adapters.human.click.echo") as mock_echo:
            asyncio.run(adapter.execute(task, [art], "trace_1"))

        stderr_calls = [
            c for c in mock_echo.call_args_list
            if c.kwargs.get("err") is True
        ]
        assert len(stderr_calls) >= 2  # header + context

    def test_input_lineage_tracks_upstream(self) -> None:
        adapter = HumanInputAdapter()
        task = self._make_input_task(node_id="feedback")
        art = _make_artifact(art_id="art_upstream")

        with patch("binex.adapters.human.click.prompt", return_value="lgtm"), \
             patch("binex.adapters.human.click.echo"):
            result = asyncio.run(adapter.execute(task, [art], "trace_1"))

        assert result.artifacts[0].lineage.produced_by == "feedback"
        assert result.artifacts[0].lineage.derived_from == ["art_upstream"]

    def test_input_health(self) -> None:
        adapter = HumanInputAdapter()
        assert asyncio.run(adapter.health()) is AgentHealth.ALIVE

    def test_input_cancel(self) -> None:
        adapter = HumanInputAdapter()
        asyncio.run(adapter.cancel("task_x"))  # should not raise
