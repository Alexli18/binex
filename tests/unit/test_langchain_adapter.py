"""Tests for LangChain framework adapter and plugin."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.langchain_adapter import LangChainAdapter, LangChainPlugin
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


def _make_task(task_id="t1", run_id="run-1", node_id="n1"):
    return TaskNode(id=task_id, run_id=run_id, node_id=node_id, agent="langchain://mod.obj")


def _make_artifact(aid="a1", run_id="run-1", content="hello"):
    return Artifact(
        id=aid, run_id=run_id, type="text", content=content,
        lineage=Lineage(produced_by="prev"),
    )


# --- Plugin tests ---

class TestLangChainPlugin:
    """Tests for LangChainPlugin."""

    def test_create_adapter_returns_langchain_adapter(self):
        """create_adapter() returns a LangChainAdapter instance."""
        plugin = LangChainPlugin()
        with patch("binex.adapters.langchain_adapter.importlib.util.find_spec", return_value=True):
            adapter = plugin.create_adapter("my_module.MyChain", {})
        assert isinstance(adapter, LangChainAdapter)

    def test_create_adapter_import_error_when_langchain_core_missing(self):
        """ImportError raised when langchain_core is not installed."""
        plugin = LangChainPlugin()
        with patch("binex.adapters.langchain_adapter.importlib.util.find_spec", return_value=None):
            with pytest.raises(ImportError, match="pip install binex\\[langchain\\]"):
                plugin.create_adapter("my_module.MyChain", {})

    def test_plugin_prefix(self):
        """Plugin has correct prefix."""
        plugin = LangChainPlugin()
        assert plugin.prefix == "langchain"

    def test_config_forwarded_to_adapter(self):
        """Config dict is forwarded from plugin to adapter."""
        plugin = LangChainPlugin()
        cfg = {"temperature": 0.5, "model": "gpt-4"}
        with patch("binex.adapters.langchain_adapter.importlib.util.find_spec", return_value=True):
            adapter = plugin.create_adapter("mod.Obj", config=cfg)
        assert adapter._config == cfg

    def test_config_defaults_to_empty_dict(self):
        """Config with empty dict is forwarded."""
        plugin = LangChainPlugin()
        with patch("binex.adapters.langchain_adapter.importlib.util.find_spec", return_value=True):
            adapter = plugin.create_adapter("mod.Obj", {})
        assert adapter._config == {}


# --- Adapter tests ---

class TestLangChainAdapter:
    """Tests for LangChainAdapter."""

    def test_adapter_prefix(self):
        """Adapter _prefix is 'langchain'."""
        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        assert adapter._prefix == "langchain"

    @pytest.mark.asyncio
    async def test_execute_with_async_ainvoke(self):
        """Execute uses ainvoke when available."""
        mock_obj = MagicMock()
        mock_obj.invoke = MagicMock()
        mock_obj.ainvoke = AsyncMock(return_value="async result")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        arts = [_make_artifact()]
        result = await adapter.execute(task, arts, trace_id="tr-1")

        mock_obj.ainvoke.assert_awaited_once_with("hello")
        mock_obj.invoke.assert_not_called()
        assert isinstance(result, ExecutionResult)
        assert result.artifacts[0].content == "async result"

    @pytest.mark.asyncio
    async def test_execute_with_sync_invoke_fallback(self):
        """Execute falls back to to_thread(invoke) when ainvoke not available."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="sync result")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        arts = [_make_artifact()]
        result = await adapter.execute(task, arts, trace_id="tr-1")

        mock_obj.invoke.assert_called_once_with("hello")
        assert result.artifacts[0].content == "sync result"

    @pytest.mark.asyncio
    async def test_single_input_artifact_content_directly(self):
        """Single input artifact passes content directly (not wrapped)."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="ok")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        arts = [_make_artifact(content="direct content")]
        await adapter.execute(task, arts, trace_id="tr-1")

        mock_obj.invoke.assert_called_once_with("direct content")

    @pytest.mark.asyncio
    async def test_multiple_input_artifacts_dict(self):
        """Multiple input artifacts passed as dict {id: content}."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="ok")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        arts = [
            _make_artifact(aid="a1", content="first"),
            _make_artifact(aid="a2", content="second"),
        ]
        await adapter.execute(task, arts, trace_id="tr-1")

        mock_obj.invoke.assert_called_once_with({"a1": "first", "a2": "second"})

    @pytest.mark.asyncio
    async def test_output_str_artifact(self):
        """String output stored as artifact content directly."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="hello world")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        result = await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

        assert result.artifacts[0].content == "hello world"

    @pytest.mark.asyncio
    async def test_output_dict_json_serialized(self):
        """Dict output is JSON-serialized."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value={"key": "value"})

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        result = await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

        assert json.loads(result.artifacts[0].content) == {"key": "value"}

    @pytest.mark.asyncio
    async def test_none_output_empty_string(self):
        """None output becomes empty string artifact."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value=None)

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        result = await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

        assert result.artifacts[0].content == ""

    @pytest.mark.asyncio
    async def test_import_nonexistent_module_runtime_error(self):
        """Importing a nonexistent module raises RuntimeError with path."""
        adapter = LangChainAdapter(import_path="nonexistent_pkg.MyObj", config={})
        task = _make_task()

        with pytest.raises(RuntimeError, match="langchain://nonexistent_pkg.MyObj"):
            await adapter.execute(task, [], trace_id="tr-1")

    @pytest.mark.asyncio
    async def test_object_missing_invoke_validation_error(self):
        """Object without .invoke raises ValueError during validation."""
        adapter = LangChainAdapter(import_path="json.dumps", config={})

        # Manually test _validate with an object that lacks .invoke
        obj_without_invoke = SimpleNamespace(name="no_invoke")
        with pytest.raises(ValueError, match="no 'invoke' method"):
            adapter._validate(obj_without_invoke)

    @pytest.mark.asyncio
    async def test_framework_exception_wrapped_runtime_error(self):
        """Framework exception is wrapped with langchain:// prefix."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(side_effect=ValueError("chain broke"))

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        with pytest.raises(RuntimeError, match="langchain://mod.Obj failed"):
            await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

    @pytest.mark.asyncio
    async def test_cancel_noop(self):
        """cancel() is a no-op and returns None."""
        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        result = await adapter.cancel("t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_health_alive(self):
        """health() returns ALIVE."""
        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        assert await adapter.health() == AgentHealth.ALIVE

    def test_lazy_load_not_on_creation(self):
        """Object is not imported on adapter creation."""
        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        assert adapter._obj is None

    @pytest.mark.asyncio
    async def test_lazy_load_on_first_execute(self):
        """Object is imported on first execute call."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="ok")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        assert adapter._obj is None

        # Pre-set the object to avoid actual import
        adapter._obj = mock_obj
        task = _make_task()
        await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

        assert adapter._obj is mock_obj

    @pytest.mark.asyncio
    async def test_artifact_lineage(self):
        """Output artifact has correct lineage metadata."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="result")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task(node_id="mynode")
        arts = [_make_artifact(aid="input1"), _make_artifact(aid="input2")]
        result = await adapter.execute(task, arts, trace_id="tr-1")

        out = result.artifacts[0]
        assert out.lineage.produced_by == "mynode"
        assert out.lineage.derived_from == ["input1", "input2"]

    @pytest.mark.asyncio
    async def test_artifact_id_format(self):
        """Output artifact id is {node_id}_output."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="x")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task(node_id="summarize")
        result = await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

        assert result.artifacts[0].id == "summarize_output"

    @pytest.mark.asyncio
    async def test_no_input_artifacts_empty_dict(self):
        """No input artifacts passes empty dict."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="ok")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        await adapter.execute(task, [], trace_id="tr-1")

        mock_obj.invoke.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_cost_is_none(self):
        """ExecutionResult cost is always None for framework adapters."""
        mock_obj = MagicMock(spec=["invoke"])
        mock_obj.invoke = MagicMock(return_value="x")

        adapter = LangChainAdapter(import_path="mod.Obj", config={})
        adapter._obj = mock_obj

        task = _make_task()
        result = await adapter.execute(task, [_make_artifact()], trace_id="tr-1")

        assert result.cost is None
