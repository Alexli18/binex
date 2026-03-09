"""Tests for error paths and edge cases in LLMAdapter and Dispatcher."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.llm import LLMAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import RetryPolicy, TaskNode
from binex.runtime.dispatcher import Dispatcher, _backoff_delay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(**overrides) -> TaskNode:
    defaults = {
        "id": "task_1",
        "run_id": "run_1",
        "node_id": "node_1",
        "agent": "llm://test-model",
    }
    defaults.update(overrides)
    return TaskNode(**defaults)


def _make_artifact(**overrides) -> Artifact:
    defaults = {
        "id": "art_1",
        "run_id": "run_1",
        "type": "text",
        "content": "hello world",
        "lineage": Lineage(produced_by="node_0"),
    }
    defaults.update(overrides)
    return Artifact(**defaults)


# ---------------------------------------------------------------------------
# LLMAdapter._build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    """Cover _build_prompt branches (lines 72, 78-82, 85)."""

    def test_prompt_template_returned_directly(self):
        """When prompt_template is set, return it verbatim (line 72)."""
        adapter = LLMAdapter(model="m", prompt_template="Do the thing.")
        task = _make_task(system_prompt="summarize", inputs={"topic": "cats"})
        result = adapter._build_prompt(task, [])
        assert result == "Do the thing."

    def test_inputs_with_unresolved_ref_skipped(self):
        """Inputs containing ${...} are skipped (lines 80-81)."""
        adapter = LLMAdapter(model="m")
        task = _make_task(
            system_prompt="summarize",
            inputs={"source": "${node.research.output}", "mode": "brief"},
        )
        result = adapter._build_prompt(task, [])
        assert "${node.research.output}" not in result
        assert "source:" not in result.lower()
        assert "mode: brief" in result

    def test_inputs_with_regular_values_included(self):
        """Regular string/non-string inputs are included (line 82)."""
        adapter = LLMAdapter(model="m")
        task = _make_task(system_prompt="translate", inputs={"lang": "fr", "count": 3})
        result = adapter._build_prompt(task, [])
        assert "lang: fr" in result
        assert "count: 3" in result


    def test_no_system_prompt_no_inputs_no_artifacts(self):
        """Empty prompt falls back to 'No input provided.' (line 85)."""
        adapter = LLMAdapter(model="m")
        task = _make_task(system_prompt=None, inputs={})
        result = adapter._build_prompt(task, [])
        assert result == "No input provided."

    def test_artifacts_appended(self):
        adapter = LLMAdapter(model="m")
        task = _make_task(system_prompt=None, inputs={})
        art = _make_artifact(type="document", content="some doc")
        result = adapter._build_prompt(task, [art])
        assert "Input (document):" in result
        assert "some doc" in result


# ---------------------------------------------------------------------------
# LLMAdapter.cancel / execute error
# ---------------------------------------------------------------------------

class TestLLMAdapterMethods:

    @pytest.mark.asyncio
    async def test_cancel_does_nothing(self):
        """cancel() is a no-op and must not raise (lines 87-88)."""
        adapter = LLMAdapter(model="m")
        result = await adapter.cancel("task_1")
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_propagates_litellm_error(self):
        """If litellm.acompletion raises, execute propagates the exception."""
        adapter = LLMAdapter(model="m")
        task = _make_task()
        with patch("binex.adapters.llm.litellm.acompletion", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("API down")
            with pytest.raises(RuntimeError, match="API down"):
                await adapter.execute(task, [], "trace_1")


# ---------------------------------------------------------------------------
# Dispatcher.get_adapter
# ---------------------------------------------------------------------------

class TestDispatcherGetAdapter:

    def test_unregistered_key_raises_key_error(self):
        d = Dispatcher()
        with pytest.raises(KeyError, match="No adapter registered for 'missing'"):
            d.get_adapter("missing")

    def test_registered_key_returns_adapter(self):
        d = Dispatcher()
        adapter = MagicMock()
        d.register_adapter("a", adapter)
        assert d.get_adapter("a") is adapter


# ---------------------------------------------------------------------------
# Dispatcher.dispatch — retries, timeouts, backoff
# ---------------------------------------------------------------------------

class TestDispatcherDispatch:

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self):
        """Adapter fails once then succeeds — dispatch returns the result."""
        d = Dispatcher()
        adapter = AsyncMock()
        adapter.execute = AsyncMock(
            side_effect=[RuntimeError("flake"), [_make_artifact()]],
        )
        d.register_adapter("agent", adapter)

        task = _make_task(
            agent="agent",
            retry_policy=RetryPolicy(max_retries=3, backoff="fixed"),
        )
        with patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock):
            result = await d.dispatch(task, [], "trace")
        assert len(result) == 1
        assert adapter.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises_last_error(self):
        """After all retries fail, the last exception is raised (line 55)."""
        d = Dispatcher()
        adapter = AsyncMock()
        adapter.execute = AsyncMock(
            side_effect=[RuntimeError("err1"), RuntimeError("err2")],
        )
        d.register_adapter("agent", adapter)

        task = _make_task(
            agent="agent",
            retry_policy=RetryPolicy(max_retries=2, backoff="fixed"),
        )
        with patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="err2"):
                await d.dispatch(task, [], "trace")

    @pytest.mark.asyncio
    async def test_deadline_timeout_raises(self):
        """When the adapter exceeds deadline_ms, TimeoutError is raised."""
        d = Dispatcher()

        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)

        adapter = AsyncMock()
        adapter.execute = slow_execute
        d.register_adapter("agent", adapter)

        task = _make_task(agent="agent", deadline_ms=1)  # 1 ms timeout
        with pytest.raises(TimeoutError):
            await d.dispatch(task, [], "trace")

    @pytest.mark.asyncio
    async def test_fixed_backoff_strategy_used(self):
        """With fixed backoff, asyncio.sleep is called with 0.1."""
        d = Dispatcher()
        adapter = AsyncMock()
        adapter.execute = AsyncMock(
            side_effect=[RuntimeError("fail"), [_make_artifact()]],
        )
        d.register_adapter("agent", adapter)

        task = _make_task(
            agent="agent",
            retry_policy=RetryPolicy(max_retries=2, backoff="fixed"),
        )
        with patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await d.dispatch(task, [], "trace")
            mock_sleep.assert_awaited_once_with(0.1)


# ---------------------------------------------------------------------------
# _backoff_delay
# ---------------------------------------------------------------------------

class TestBackoffDelay:

    def test_fixed_returns_point_one(self):
        """Fixed strategy always returns 0.1 (line 61)."""
        assert _backoff_delay(1, "fixed") == 0.1
        assert _backoff_delay(5, "fixed") == 0.1

    def test_exponential_attempt_1(self):
        """Exponential: attempt 1 -> 2^0 * 0.1 = 0.1."""
        assert _backoff_delay(1, "exponential") == pytest.approx(0.1)

    def test_exponential_attempt_2(self):
        """Exponential: attempt 2 -> 2^1 * 0.1 = 0.2."""
        assert _backoff_delay(2, "exponential") == pytest.approx(0.2)

    def test_exponential_capped_at_10(self):
        """Exponential backoff is capped at 10.0 seconds."""
        assert _backoff_delay(100, "exponential") == 10.0
