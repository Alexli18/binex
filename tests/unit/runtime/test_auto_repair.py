"""Auto-repair ladder (issue #65): deterministic repair, structured output, feedback loop."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.llm import LLMAdapter
from binex.models.task import TaskNode
from binex.models.workflow import RepairConfig
from binex.runtime.json_repair import repair_json_text
from binex.runtime.schema_validator import validate_output

_SCHEMA = {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}}


def _make_task(**config) -> TaskNode:
    return TaskNode(
        id="task-1", run_id="run-1", node_id="node-1",
        agent="llm://gpt-4o", system_prompt="produce json", config=config,
    )


def _resp(content: str) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    r.choices[0].message.tool_calls = None
    return r


# ── Step 1: deterministic repair ────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ('```json\n{"x": 1}\n```', '{"x": 1}'),
    ('Here is the JSON: {"x": 1} done', '{"x": 1}'),
    ('{"x": 1,}', '{"x": 1}'),          # trailing comma
    ('```\n[1, 2, 3]\n```', '[1, 2, 3]'),
    ('{"k": "a{b}c"}', '{"k": "a{b}c"}'),  # braces inside string
])
def test_repair_json_text(raw, expected):
    assert repair_json_text(raw) == expected


def test_repair_json_text_unrecoverable():
    assert repair_json_text("no json here at all") is None


def test_validate_output_applies_repair():
    v = validate_output('```json\n{"x": 5}\n```', _SCHEMA)
    assert v.valid is True
    assert v.repaired is True
    assert v.normalized == {"x": 5}


def test_validate_output_clean_input_not_flagged_repaired():
    v = validate_output('{"x": 5}', _SCHEMA)
    assert v.valid is True and v.repaired is False


# ── RepairConfig model ──────────────────────────────────────────────────

def test_repair_config_defaults():
    c = RepairConfig()
    assert c.max_attempts == 0 and c.escalate is False


def test_repair_config_rejects_negative():
    with pytest.raises(ValueError, match="max_attempts"):
        RepairConfig(max_attempts=-1)


# ── Step 2: native structured output ────────────────────────────────────

@pytest.mark.asyncio
async def test_native_structured_output_added_when_supported():
    adapter = LLMAdapter(model="gpt-4o")
    task = _make_task(output_schema=_SCHEMA)

    with patch("binex.adapters.llm.litellm.supports_response_schema", return_value=True), \
         patch("binex.adapters.llm.litellm.acompletion",
               new_callable=AsyncMock, return_value=_resp('{"x": 1}')) as mock_llm:
        await adapter.execute(task, [], "trace-1")

    kwargs = mock_llm.call_args.kwargs
    assert "response_format" in kwargs
    assert kwargs["response_format"]["json_schema"]["schema"] == _SCHEMA


@pytest.mark.asyncio
async def test_native_structured_output_skipped_when_unsupported():
    adapter = LLMAdapter(model="some/local-model")
    task = _make_task(output_schema=_SCHEMA)

    with patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False), \
         patch("binex.adapters.llm.litellm.acompletion",
               new_callable=AsyncMock, return_value=_resp('{"x": 1}')) as mock_llm:
        await adapter.execute(task, [], "trace-1")

    assert "response_format" not in mock_llm.call_args.kwargs


# ── Step 3: feedback loop ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feedback_loop_repairs_on_second_attempt():
    adapter = LLMAdapter(model="gpt-4o")
    task = _make_task(output_schema=_SCHEMA, repair={"max_attempts": 2})

    responses = [_resp('{"wrong": true}'), _resp('{"x": 42}')]
    with patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False), \
         patch("binex.adapters.llm.litellm.acompletion",
               new_callable=AsyncMock, side_effect=responses):
        result = await adapter.execute(task, [], "trace-1")

    art = result.artifacts[0]
    assert art.content == '{"x": 42}'
    assert art.metadata["repair_attempts"] == 1
    assert art.metadata["repair_step"] == "feedback"


@pytest.mark.asyncio
async def test_feedback_loop_exhaustion_flags_failure():
    adapter = LLMAdapter(model="gpt-4o")
    task = _make_task(output_schema=_SCHEMA, repair={"max_attempts": 2})

    bad = [_resp('{"nope": 1}'), _resp('{"still": 2}'), _resp('{"bad": 3}')]
    with patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False), \
         patch("binex.adapters.llm.litellm.acompletion",
               new_callable=AsyncMock, side_effect=bad):
        result = await adapter.execute(task, [], "trace-1")

    meta = result.artifacts[0].metadata
    assert meta["repaired"] is False
    assert meta["repair_attempts"] == 2
    assert meta["validation_errors"]


@pytest.mark.asyncio
async def test_deterministic_repair_avoids_model_call():
    """Fenced-but-valid JSON is fixed with zero extra model calls."""
    adapter = LLMAdapter(model="gpt-4o")
    task = _make_task(output_schema=_SCHEMA, repair={"max_attempts": 2})

    with patch("binex.adapters.llm.litellm.supports_response_schema", return_value=False), \
         patch("binex.adapters.llm.litellm.acompletion",
               new_callable=AsyncMock, return_value=_resp('```json\n{"x": 7}\n```')) as mock_llm:
        result = await adapter.execute(task, [], "trace-1")

    assert mock_llm.call_count == 1  # no feedback round needed
    art = result.artifacts[0]
    assert art.content == '{"x": 7}'
    assert art.metadata["repair_step"] == "deterministic"
