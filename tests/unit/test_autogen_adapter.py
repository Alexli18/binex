"""Tests for AutoGen framework adapter and plugin."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.autogen_adapter import AutoGenAdapter, AutoGenPlugin
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id="t1", run_id="run-1", node_id="n1"):
    return TaskNode(id=task_id, run_id=run_id, node_id=node_id, agent="autogen://mod.obj")


def _make_artifact(aid="a1", run_id="run-1", content="hello"):
    return Artifact(
        id=aid, run_id=run_id, type="text", content=content,
        lineage=Lineage(produced_by="prev"),
    )


# ---------------------------------------------------------------------------
# Plugin tests
# ---------------------------------------------------------------------------

class TestAutoGenPlugin:
    def test_plugin_prefix(self):
        plugin = AutoGenPlugin()
        assert plugin.prefix == "autogen"

    def test_create_adapter_returns_autogen_adapter(self):
        plugin = AutoGenPlugin()
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = plugin.create_adapter("mod.Agent", {"temperature": 0.5})
        assert isinstance(adapter, AutoGenAdapter)

    def test_create_adapter_import_error_when_not_installed(self):
        plugin = AutoGenPlugin()
        with patch("importlib.util.find_spec", return_value=None):
            with pytest.raises(ImportError, match="pip install binex\\[autogen\\]"):
                plugin.create_adapter("mod.Agent", {})

    def test_config_forwarding(self):
        plugin = AutoGenPlugin()
        cfg = {"temperature": 0.7, "max_tokens": 100}
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = plugin.create_adapter("mod.Agent", cfg)
        assert adapter._config == cfg

    def test_import_path_forwarding(self):
        plugin = AutoGenPlugin()
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = plugin.create_adapter("mypackage.agents.MyAgent", {})
        assert adapter._import_path == "mypackage.agents.MyAgent"


# ---------------------------------------------------------------------------
# Adapter — validation
# ---------------------------------------------------------------------------

class TestAutoGenAdapterValidation:
    def test_validate_object_with_run(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        obj = MagicMock(spec=["run"])
        # Should not raise
        adapter._validate(obj)

    def test_validate_object_missing_run_raises(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        obj = MagicMock(spec=[])  # no 'run' attribute
        with pytest.raises(ValueError, match="run"):
            adapter._validate(obj)

    def test_prefix_is_autogen(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        assert adapter._prefix == "autogen"


# ---------------------------------------------------------------------------
# Adapter — _invoke
# ---------------------------------------------------------------------------

class TestAutoGenAdapterInvoke:
    @pytest.mark.asyncio
    async def test_invoke_uses_a_run_when_available(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        obj = MagicMock()
        obj.a_run = AsyncMock(return_value="async result")
        result = await adapter._invoke(obj, "do something")
        obj.a_run.assert_awaited_once_with(task="do something")
        assert result == "async result"

    @pytest.mark.asyncio
    async def test_invoke_falls_back_to_sync_run(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        obj = MagicMock(spec=["run"])
        obj.run.return_value = "sync result"
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value="sync result") as mock_thread:
            result = await adapter._invoke(obj, "task input")
        mock_thread.assert_awaited_once_with(obj.run, task="task input")
        assert result == "sync result"


# ---------------------------------------------------------------------------
# Adapter — _extract_output
# ---------------------------------------------------------------------------

class TestAutoGenAdapterExtractOutput:
    def test_extract_string_message(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = MagicMock()
        result.messages = ["first", "last message"]
        assert adapter._extract_output(result) == "last message"

    def test_extract_dict_message_with_content(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = MagicMock()
        result.messages = [{"content": "answer text", "role": "assistant"}]
        assert adapter._extract_output(result) == "answer text"

    def test_extract_dict_message_without_content(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = MagicMock()
        msg = {"role": "assistant", "tool_calls": []}
        result.messages = [msg]
        assert adapter._extract_output(result) == str(msg)

    def test_extract_non_string_non_dict_message(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = MagicMock()
        inner = MagicMock()
        inner.__str__ = lambda self: "custom_msg"
        result.messages = [inner]
        assert adapter._extract_output(result) == "custom_msg"

    def test_extract_empty_messages_uses_str(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = MagicMock()
        result.messages = []
        output = adapter._extract_output(result)
        assert output == str(result)

    def test_extract_none_result(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        assert adapter._extract_output(None) == ""

    def test_extract_no_messages_attr(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = MagicMock(spec=[])  # no messages attribute
        assert adapter._extract_output(result) == str(result)


# ---------------------------------------------------------------------------
# Adapter — execute (end-to-end)
# ---------------------------------------------------------------------------

class TestAutoGenAdapterExecute:
    @pytest.mark.asyncio
    async def test_execute_single_input(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        task = _make_task()
        art = _make_artifact(content="summarize this")

        mock_result = MagicMock()
        mock_result.messages = ["Summary done"]

        fake_module = MagicMock()
        fake_obj = MagicMock()
        fake_obj.a_run = AsyncMock(return_value=mock_result)
        fake_module.Agent = fake_obj

        with patch("importlib.import_module", return_value=fake_module):
            result = await adapter.execute(task, [art], "trace-1")

        assert isinstance(result, ExecutionResult)
        assert result.artifacts[0].content == "Summary done"

    @pytest.mark.asyncio
    async def test_execute_multiple_inputs_as_dict(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        task = _make_task()
        a1 = _make_artifact(aid="x", content="c1")
        a2 = _make_artifact(aid="y", content="c2")

        mock_result = MagicMock()
        mock_result.messages = ["combined"]

        fake_module = MagicMock()
        fake_obj = MagicMock()
        fake_obj.a_run = AsyncMock(return_value=mock_result)
        fake_module.Agent = fake_obj

        with patch("importlib.import_module", return_value=fake_module):
            result = await adapter.execute(task, [a1, a2], "trace-1")

        # a_run should have been called with dict input
        call_kwargs = fake_obj.a_run.call_args
        assert call_kwargs == ((), {"task": {"x": "c1", "y": "c2"}})

    @pytest.mark.asyncio
    async def test_execute_dict_output_normalized_to_json(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        task = _make_task()
        art = _make_artifact()

        mock_result = MagicMock()
        mock_result.messages = [{"content": {"key": "val"}}]

        fake_module = MagicMock()
        fake_obj = MagicMock()
        fake_obj.a_run = AsyncMock(return_value=mock_result)
        fake_module.Agent = fake_obj

        with patch("importlib.import_module", return_value=fake_module):
            result = await adapter.execute(task, [art], "trace-1")

        # dict content is extracted, then _normalize_output converts to JSON
        parsed = json.loads(result.artifacts[0].content)
        assert parsed == {"key": "val"}

    @pytest.mark.asyncio
    async def test_execute_framework_exception_wrapped(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        task = _make_task()
        art = _make_artifact()

        fake_module = MagicMock()
        fake_obj = MagicMock()
        fake_obj.a_run = AsyncMock(side_effect=ValueError("agent blew up"))
        fake_module.Agent = fake_obj

        with patch("importlib.import_module", return_value=fake_module):
            with pytest.raises(RuntimeError, match="autogen://"):
                await adapter.execute(task, [art], "trace-1")


# ---------------------------------------------------------------------------
# Adapter — cancel and health
# ---------------------------------------------------------------------------

class TestAutoGenAdapterCancelHealth:
    @pytest.mark.asyncio
    async def test_cancel_is_noop(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        result = await adapter.cancel("some-task")
        assert result is None

    @pytest.mark.asyncio
    async def test_health_returns_alive(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        assert await adapter.health() == AgentHealth.ALIVE


# ---------------------------------------------------------------------------
# Adapter — lazy load
# ---------------------------------------------------------------------------

class TestAutoGenAdapterLazyLoad:
    def test_lazy_load_caches_object(self):
        adapter = AutoGenAdapter("mod.Agent", {})
        fake_module = MagicMock()
        fake_module.Agent = MagicMock(spec=["run"])

        with patch("importlib.import_module", return_value=fake_module) as mock_import:
            first = adapter._load_object()
            second = adapter._load_object()
            assert first is second
            mock_import.assert_called_once()

    def test_import_error_wrapped_with_prefix(self):
        adapter = AutoGenAdapter("bad.module.Agent", {})
        with patch("importlib.import_module", side_effect=ImportError("No module")):
            with pytest.raises(RuntimeError, match="autogen://"):
                adapter._load_object()
