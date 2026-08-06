"""Tests for ScriptedInputAdapter."""

from __future__ import annotations

import pytest

from binex.adapters.scripted_input import ScriptedInputAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


def _make_task(node_id: str = "ask_user") -> TaskNode:
    return TaskNode(
        id=f"task_{node_id}",
        node_id=node_id,
        run_id="run-test",
        agent="human://input",
        system_prompt="What is your name?",
    )


def _make_artifact(art_id: str = "art_001") -> Artifact:
    return Artifact(
        id=art_id,
        run_id="run-test",
        type="text",
        content="upstream",
        lineage=Lineage(produced_by="prev_node", derived_from=[]),
    )


@pytest.mark.asyncio
async def test_node_id_match():
    adapter = ScriptedInputAdapter({"ask_user": "Alice", "other": "Bob"})
    result = await adapter.execute(_make_task("ask_user"), [], "trace-1")
    assert len(result.artifacts) == 1
    assert result.artifacts[0].content == "Alice"
    assert result.artifacts[0].type == "human_input"


@pytest.mark.asyncio
async def test_single_entry_fallback():
    adapter = ScriptedInputAdapter({"any_key": "fallback_value"})
    result = await adapter.execute(_make_task("unknown_node"), [], "trace-1")
    assert result.artifacts[0].content == "fallback_value"


@pytest.mark.asyncio
async def test_missing_value_raises():
    adapter = ScriptedInputAdapter({"node_a": "val_a", "node_b": "val_b"})
    with pytest.raises(ValueError, match="no preset value for node"):
        await adapter.execute(_make_task("unknown_node"), [], "trace-1")


@pytest.mark.asyncio
async def test_lineage_tracks_upstream_artifacts():
    upstream = _make_artifact("art_upstream")
    adapter = ScriptedInputAdapter({"ask_user": "response"})
    result = await adapter.execute(_make_task("ask_user"), [upstream], "trace-1")
    assert "art_upstream" in result.artifacts[0].lineage.derived_from


@pytest.mark.asyncio
async def test_artifact_run_id_matches_task():
    adapter = ScriptedInputAdapter({"ask_user": "value"})
    task = _make_task("ask_user")
    result = await adapter.execute(task, [], "trace-1")
    assert result.artifacts[0].run_id == task.run_id


@pytest.mark.asyncio
async def test_health_returns_alive():
    from binex.models.agent import AgentHealth

    adapter = ScriptedInputAdapter({})
    assert await adapter.health() == AgentHealth.ALIVE


@pytest.mark.asyncio
async def test_cancel_is_noop():
    adapter = ScriptedInputAdapter({})
    await adapter.cancel("task-1")  # must not raise
