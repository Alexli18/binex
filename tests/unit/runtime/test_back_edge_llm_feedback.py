"""Tests for LLMAdapter feedback artifact formatting in prompts."""
from __future__ import annotations

from binex.adapters.llm import LLMAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


def _make_task() -> TaskNode:
    return TaskNode(
        id="run1_gen",
        run_id="run1",
        node_id="generate",
        agent="llm://test",
        system_prompt="You are a writer.",
        tools=[],
        inputs={},
    )


def _make_artifact(art_type: str = "result", content: str = "hello") -> Artifact:
    return Artifact(
        id="art_1",
        run_id="run1",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="upstream"),
    )


class TestFeedbackFormatting:
    def test_regular_artifact_formatted_as_input(self) -> None:
        adapter = LLMAdapter(model="test")
        task = _make_task()
        art = _make_artifact(art_type="result", content="some data")
        prompt = adapter._build_prompt(task, [art])
        assert "Input (result):" in prompt
        assert "some data" in prompt

    def test_feedback_artifact_formatted_distinctly(self) -> None:
        adapter = LLMAdapter(model="test")
        task = _make_task()
        art = _make_artifact(art_type="feedback", content="fix the intro")
        prompt = adapter._build_prompt(task, [art])
        assert "previous output was rejected" in prompt.lower()
        assert "fix the intro" in prompt

    def test_feedback_and_regular_mixed(self) -> None:
        adapter = LLMAdapter(model="test")
        task = _make_task()
        regular = _make_artifact(art_type="result", content="draft text")
        feedback = _make_artifact(art_type="feedback", content="too formal")
        prompt = adapter._build_prompt(task, [regular, feedback])
        assert "Input (result):" in prompt
        assert "draft text" in prompt
        assert "too formal" in prompt
        assert "previous output was rejected" in prompt.lower()

    def test_no_feedback_works_as_before(self) -> None:
        adapter = LLMAdapter(model="test")
        task = _make_task()
        art = _make_artifact(art_type="llm_response", content="data")
        prompt = adapter._build_prompt(task, [art])
        assert "Input (llm_response):" in prompt
        assert "rejected" not in prompt.lower()
