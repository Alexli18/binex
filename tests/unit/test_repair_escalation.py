"""Repair escalation (#67): promote to a stronger model when schema repair fails."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from binex.adapters.llm import LLMAdapter
from binex.models.task import TaskNode

_SCHEMA = {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}}


def _task(**config) -> TaskNode:
    return TaskNode(
        id="t", run_id="r", node_id="n", agent="llm://gpt-4o",
        system_prompt="produce json", config=config,
    )


def _resp(content: str) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    r.choices[0].message.tool_calls = None
    return r


def _by_model(responses: dict[str, list]):
    """A fake _completion_with_retry that serves per-model queued responses."""
    async def _fn(**kwargs):
        model = kwargs["model"]
        return responses[model].pop(0)
    return _fn


@pytest.mark.asyncio
async def test_escalates_to_next_model_on_repair_exhaustion():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(
        output_schema=_SCHEMA,
        repair={"max_attempts": 2, "escalate": True},
        fallbacks=["big/claude"],
    )
    # gpt-4o: initial + 2 feedback attempts, all invalid. claude: escalation, valid.
    responses = {
        "gpt-4o": [_resp('{"no": 1}'), _resp('{"no": 2}'), _resp('{"no": 3}')],
        "big/claude": [_resp('{"x": 42}')],
    }
    with patch.object(adapter, "_completion_with_retry", side_effect=_by_model(responses)), \
         patch("binex.adapters.llm.litellm.completion_cost", return_value=0.0), \
         patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False):
        result = await adapter.execute(task, [], "trace-1")

    meta = result.artifacts[0].metadata
    assert result.artifacts[0].content == '{"x": 42}'
    assert meta["escalated"] == "schema_repair_exhausted"
    assert meta["escalated_to"] == "big/claude"
    assert meta["actual_model"] == "big/claude"


@pytest.mark.asyncio
async def test_no_escalation_when_flag_off():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(
        output_schema=_SCHEMA,
        repair={"max_attempts": 2, "escalate": False},
        fallbacks=["big/claude"],
    )
    responses = {"gpt-4o": [_resp('{"no": 1}'), _resp('{"no": 2}'), _resp('{"no": 3}')]}
    with patch.object(adapter, "_completion_with_retry", side_effect=_by_model(responses)), \
         patch("binex.adapters.llm.litellm.completion_cost", return_value=0.0), \
         patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False):
        result = await adapter.execute(task, [], "trace-1")

    meta = result.artifacts[0].metadata
    assert meta["repaired"] is False       # stayed exhausted
    assert "escalated" not in meta
    assert meta["actual_model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_no_fallback_env_disables_escalation(monkeypatch):
    monkeypatch.setenv("BINEX_NO_FALLBACK", "1")
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(
        output_schema=_SCHEMA,
        repair={"max_attempts": 2, "escalate": True},
        fallbacks=["big/claude"],
    )
    responses = {"gpt-4o": [_resp('{"no": 1}'), _resp('{"no": 2}'), _resp('{"no": 3}')]}
    with patch.object(adapter, "_completion_with_retry", side_effect=_by_model(responses)), \
         patch("binex.adapters.llm.litellm.completion_cost", return_value=0.0), \
         patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False):
        result = await adapter.execute(task, [], "trace-1")

    assert "escalated" not in result.artifacts[0].metadata


@pytest.mark.asyncio
async def test_escalation_all_exhausted_keeps_last():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(
        output_schema=_SCHEMA,
        repair={"max_attempts": 1, "escalate": True},
        fallbacks=["big/claude"],
    )
    # Both models fail repair entirely.
    responses = {
        "gpt-4o": [_resp('{"a": 1}'), _resp('{"a": 2}')],       # initial + 1 feedback
        "big/claude": [_resp('{"b": 1}'), _resp('{"b": 2}')],   # escalation + 1 feedback
    }
    with patch.object(adapter, "_completion_with_retry", side_effect=_by_model(responses)), \
         patch("binex.adapters.llm.litellm.completion_cost", return_value=0.0), \
         patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False):
        result = await adapter.execute(task, [], "trace-1")

    meta = result.artifacts[0].metadata
    assert meta["escalated"] == "schema_repair_exhausted"
    assert meta["escalated_to"] == "big/claude"
    assert meta["repaired"] is False       # still invalid after escalation
