"""Tests for Web UI human adapters."""

from __future__ import annotations

import asyncio

import pytest

from binex.adapters.web_human import WebHumanApprovalAdapter, WebHumanInputAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.ui.api.events import EventBus
from binex.ui.api.prompts import PendingPrompts


def _make_task(node_id: str = "review", run_id: str = "run-1", **kwargs) -> TaskNode:
    defaults = dict(
        id=f"task-{node_id}",
        node_id=node_id,
        run_id=run_id,
        agent="human://approve",
    )
    defaults.update(kwargs)
    return TaskNode(**defaults)


def _make_artifact(art_id: str = "art-1", run_id: str = "run-1") -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type="result",
        content="Test content for review",
        lineage=Lineage(produced_by="upstream", derived_from=[]),
    )


class TestWebHumanApprovalAdapter:
    @pytest.mark.asyncio
    async def test_approve(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanApprovalAdapter(bus, prompts)
        task = _make_task()
        artifacts = [_make_artifact()]

        # Subscribe to capture SSE events
        queue = bus.subscribe("run-1")

        # Run adapter in background, respond after SSE event
        async def respond_after_prompt():
            event = await queue.get()
            assert event["type"] == "human:prompt_needed"
            assert event["prompt_type"] == "approval"
            assert event["node_id"] == "review"
            prompt_id = event["prompt_id"]
            prompts.respond(prompt_id, {"action": "approve", "text": ""})

        responder = asyncio.create_task(respond_after_prompt())
        result = await adapter.execute(task, artifacts, "trace-1")
        await responder

        assert len(result.artifacts) == 1
        assert result.artifacts[0].type == "decision"
        assert result.artifacts[0].content == "approved"
        assert result.artifacts[0].lineage.produced_by == "review"

    @pytest.mark.asyncio
    async def test_reject_with_feedback(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanApprovalAdapter(bus, prompts)
        task = _make_task()
        artifacts = [_make_artifact()]

        queue = bus.subscribe("run-1")

        async def respond_reject():
            event = await queue.get()
            prompts.respond(event["prompt_id"], {
                "action": "reject",
                "text": "Needs more detail",
            })

        responder = asyncio.create_task(respond_reject())
        result = await adapter.execute(task, artifacts, "trace-1")
        await responder

        assert len(result.artifacts) == 2
        assert result.artifacts[0].type == "decision"
        assert result.artifacts[0].content == "rejected"
        assert result.artifacts[1].type == "feedback"
        assert result.artifacts[1].content == "Needs more detail"

    @pytest.mark.asyncio
    async def test_reject_without_feedback(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanApprovalAdapter(bus, prompts)
        task = _make_task()
        artifacts = [_make_artifact()]

        queue = bus.subscribe("run-1")

        async def respond_reject():
            event = await queue.get()
            prompts.respond(event["prompt_id"], {"action": "reject", "text": ""})

        responder = asyncio.create_task(respond_reject())
        result = await adapter.execute(task, artifacts, "trace-1")
        await responder

        # No feedback artifact when text is empty
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "rejected"

    @pytest.mark.asyncio
    async def test_publishes_artifacts_context(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanApprovalAdapter(bus, prompts)
        task = _make_task()
        artifacts = [_make_artifact("art-a"), _make_artifact("art-b")]

        queue = bus.subscribe("run-1")

        async def check_and_respond():
            event = await queue.get()
            assert len(event["artifacts"]) == 2
            assert event["artifacts"][0]["id"] == "art-a"
            assert event["artifacts"][1]["id"] == "art-b"
            prompts.respond(event["prompt_id"], {"action": "approve", "text": ""})

        responder = asyncio.create_task(check_and_respond())
        await adapter.execute(task, artifacts, "trace-1")
        await responder

    @pytest.mark.asyncio
    async def test_health(self):
        from binex.models.agent import AgentHealth

        adapter = WebHumanApprovalAdapter(EventBus(), PendingPrompts())
        assert await adapter.health() == AgentHealth.ALIVE

    @pytest.mark.asyncio
    async def test_cancel(self):
        adapter = WebHumanApprovalAdapter(EventBus(), PendingPrompts())
        await adapter.cancel("task-1")  # Should not raise


class TestWebHumanInputAdapter:
    @pytest.mark.asyncio
    async def test_input(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanInputAdapter(bus, prompts)
        task = _make_task(
            node_id="user_input",
            agent="human://input",
            system_prompt="What topic?",
        )

        queue = bus.subscribe("run-1")

        async def respond_input():
            event = await queue.get()
            assert event["type"] == "human:prompt_needed"
            assert event["prompt_type"] == "input"
            assert event["message"] == "What topic?"
            prompts.respond(event["prompt_id"], {"action": "input", "text": "AI safety"})

        responder = asyncio.create_task(respond_input())
        result = await adapter.execute(task, [], "trace-1")
        await responder

        assert len(result.artifacts) == 1
        assert result.artifacts[0].type == "human_input"
        assert result.artifacts[0].content == "AI safety"
        assert result.artifacts[0].lineage.produced_by == "user_input"

    @pytest.mark.asyncio
    async def test_default_prompt_message(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanInputAdapter(bus, prompts)
        task = _make_task(node_id="inp", agent="human://input")

        queue = bus.subscribe("run-1")

        async def respond():
            event = await queue.get()
            assert event["message"] == "Enter your input"
            prompts.respond(event["prompt_id"], {"action": "input", "text": "hello"})

        responder = asyncio.create_task(respond())
        await adapter.execute(task, [], "trace-1")
        await responder

    @pytest.mark.asyncio
    async def test_lineage_from_input_artifacts(self):
        bus = EventBus()
        prompts = PendingPrompts()
        adapter = WebHumanInputAdapter(bus, prompts)
        task = _make_task(node_id="inp", agent="human://input")
        artifacts = [_make_artifact("art-x"), _make_artifact("art-y")]

        queue = bus.subscribe("run-1")

        async def respond():
            event = await queue.get()
            prompts.respond(event["prompt_id"], {"action": "input", "text": "test"})

        responder = asyncio.create_task(respond())
        result = await adapter.execute(task, artifacts, "trace-1")
        await responder

        assert result.artifacts[0].lineage.derived_from == ["art-x", "art-y"]
