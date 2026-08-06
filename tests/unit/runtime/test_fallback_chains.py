"""Model fallback chains (issue #66)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from binex.adapters.llm import LLMAdapter, _fallback_reason
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec


class _HttpError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status_code = status


def _task(**config) -> TaskNode:
    return TaskNode(
        id="t", run_id="r", node_id="n", agent="llm://gpt-4o",
        system_prompt="do", config=config,
    )


def _resp(content: str) -> MagicMock:
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message.content = content
    r.choices[0].message.tool_calls = None
    return r


# ── error classification ─────────────────────────────────────────────────

@pytest.mark.parametrize("status,expected", [
    (429, "rate_limited"),
    (401, "auth_error"),
    (500, "server_error"),
    (503, "server_error"),
    (400, None),   # bad request is not a fallback trigger
    (404, None),   # (NotFoundError type is matched elsewhere; bare 404 isn't)
])
def test_fallback_reason_by_status(status, expected):
    assert _fallback_reason(_HttpError(status)) == expected


def test_fallback_reason_non_http_error_is_none():
    assert _fallback_reason(ValueError("bad json")) is None


# ── _complete_with_fallback ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_used_on_retriable_error():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(fallbacks=["ollama/llama3"])
    ok = _resp("done")
    with patch.object(adapter, "_completion_with_retry",
                      side_effect=[_HttpError(429), ok]):
        resp, actual, events = await adapter._complete_with_fallback({}, task)
    assert resp is ok
    assert actual == "ollama/llama3"
    assert events[0] == {"from": "gpt-4o", "to": "ollama/llama3", "reason": "rate_limited"}


@pytest.mark.asyncio
async def test_no_fallback_on_non_retriable_error():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(fallbacks=["ollama/llama3"])
    with patch.object(adapter, "_completion_with_retry",
                      side_effect=[_HttpError(400), _resp("unused")]):
        with pytest.raises(_HttpError):
            await adapter._complete_with_fallback({}, task)


@pytest.mark.asyncio
async def test_no_fallback_env_disables_chain(monkeypatch):
    monkeypatch.setenv("BINEX_NO_FALLBACK", "1")
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(fallbacks=["ollama/llama3"])
    with patch.object(adapter, "_completion_with_retry", side_effect=[_HttpError(429)]):
        with pytest.raises(_HttpError):
            await adapter._complete_with_fallback({}, task)


# ── execute() surfaces requested/actual model ────────────────────────────

@pytest.mark.asyncio
async def test_execute_records_fallback_in_metadata():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task(fallbacks=["ollama/llama3"])
    with patch.object(adapter, "_completion_with_retry",
                      side_effect=[_HttpError(503), _resp("hello")]), \
         patch("binex.adapters.llm.litellm.completion_cost", return_value=0.0):
        result = await adapter.execute(task, [], "trace-1")
    meta = result.artifacts[0].metadata
    assert meta["requested_model"] == "gpt-4o"
    assert meta["actual_model"] == "ollama/llama3"
    assert meta["fallbacks"][0]["reason"] == "server_error"


@pytest.mark.asyncio
async def test_execute_no_fallback_records_same_model():
    adapter = LLMAdapter(model="gpt-4o")
    task = _task()
    with patch.object(adapter, "_completion_with_retry", return_value=_resp("hi")), \
         patch("binex.adapters.llm.litellm.completion_cost", return_value=0.0):
        result = await adapter.execute(task, [], "trace-1")
    meta = result.artifacts[0].metadata
    assert meta["requested_model"] == meta["actual_model"] == "gpt-4o"
    assert "fallbacks" not in meta


# ── model field parsing + validate advisory ──────────────────────────────

def test_nodespec_fallbacks_default_empty():
    node = NodeSpec(agent="llm://gpt-4o", outputs=["r"])
    assert node.fallbacks == []


def test_check_fallback_chains_warns_on_smaller_context():
    from binex.workflow_spec.validator import check_fallback_chains

    spec = WorkflowSpec(
        name="w",
        nodes={"a": NodeSpec(
            agent="llm://gpt-4o", outputs=["r"], fallbacks=["small-model"],
        )},
    )

    def _info(model):
        return {"max_input_tokens": 128000 if model == "gpt-4o" else 4096}

    with patch("litellm.get_model_info", side_effect=_info), \
         patch("litellm.supports_function_calling", return_value=True):
        warnings = check_fallback_chains(spec)
    assert any("smaller context" in w for w in warnings)


def test_check_fallback_chains_warns_on_missing_tools_support():
    from binex.workflow_spec.validator import check_fallback_chains

    spec = WorkflowSpec(
        name="w",
        nodes={"a": NodeSpec(
            agent="llm://gpt-4o", outputs=["r"],
            fallbacks=["no-tools-model"], tools=["builtin://calculator"],
        )},
    )
    with patch("litellm.get_model_info", return_value={"max_input_tokens": 8000}), \
         patch("litellm.supports_function_calling", return_value=False):
        warnings = check_fallback_chains(spec)
    assert any("lacks function-calling" in w for w in warnings)


def test_execution_record_roundtrip_models(tmp_path):
    import asyncio

    from binex.models.execution import ExecutionRecord
    from binex.models.task import TaskStatus
    from binex.stores.backends.sqlite import SqliteExecutionStore

    async def _go():
        store = SqliteExecutionStore(os.path.join(tmp_path, "b.db"))
        await store.record(ExecutionRecord(
            id="rec1", run_id="r", task_id="n", agent_id="llm://gpt-4o",
            status=TaskStatus.COMPLETED, latency_ms=1, trace_id="t",
            requested_model="gpt-4o", actual_model="claude",
        ))
        recs = await store.list_records("r")
        await store.close()
        return recs

    recs = asyncio.run(_go())
    assert recs[0].requested_model == "gpt-4o"
    assert recs[0].actual_model == "claude"
