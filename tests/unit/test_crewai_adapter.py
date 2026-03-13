"""Tests for CrewAI framework adapter and plugin."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.crewai_adapter import CrewAIAdapter, CrewAIPlugin
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id="t1", run_id="run-1", node_id="n1"):
    return TaskNode(id=task_id, run_id=run_id, node_id=node_id, agent="crewai://mod.obj")


def _make_artifact(aid="a1", run_id="run-1", content="hello"):
    return Artifact(
        id=aid, run_id=run_id, type="text", content=content,
        lineage=Lineage(produced_by="prev"),
    )


def _crew_mock(*, has_async=True, result="crew output"):
    """Return a mock crew object with kickoff and optionally kickoff_async."""
    crew = MagicMock()
    crew.kickoff = MagicMock(return_value=result)
    if has_async:
        crew.kickoff_async = AsyncMock(return_value=result)
    else:
        del crew.kickoff_async
    return crew


def _adapter_with_obj(obj):
    """Create a CrewAIAdapter with a pre-loaded object (bypass import)."""
    adapter = CrewAIAdapter("mod.Crew", {})
    adapter._obj = obj
    return adapter


# ---------------------------------------------------------------------------
# CrewAIPlugin tests
# ---------------------------------------------------------------------------

class TestCrewAIPlugin:
    def test_create_adapter_returns_crewai_adapter(self):
        plugin = CrewAIPlugin()
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = plugin.create_adapter("mymod.MyCrew", {})
        assert isinstance(adapter, CrewAIAdapter)

    def test_create_adapter_import_error_when_crewai_missing(self):
        plugin = CrewAIPlugin()
        with patch("importlib.util.find_spec", return_value=None):
            with pytest.raises(ImportError, match="pip install binex\\[crewai\\]"):
                plugin.create_adapter("mymod.MyCrew", {})

    def test_plugin_prefix_is_crewai(self):
        plugin = CrewAIPlugin()
        assert plugin.prefix == "crewai"

    def test_create_adapter_forwards_config(self):
        plugin = CrewAIPlugin()
        cfg = {"temperature": 0.5}
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = plugin.create_adapter("mymod.MyCrew", cfg)
        assert adapter._config == cfg

    def test_create_adapter_forwards_import_path(self):
        plugin = CrewAIPlugin()
        with patch("importlib.util.find_spec", return_value=MagicMock()):
            adapter = plugin.create_adapter("pkg.mod.Crew", {})
        assert adapter._import_path == "pkg.mod.Crew"


# ---------------------------------------------------------------------------
# CrewAIAdapter._validate tests
# ---------------------------------------------------------------------------

class TestCrewAIValidate:
    def test_valid_object_with_kickoff(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        obj = MagicMock()
        obj.kickoff = MagicMock()
        # Should not raise
        adapter._validate(obj)

    def test_missing_kickoff_raises_value_error(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        obj = MagicMock(spec=[])  # no kickoff
        with pytest.raises(ValueError, match="kickoff"):
            adapter._validate(obj)


# ---------------------------------------------------------------------------
# CrewAIAdapter._invoke tests
# ---------------------------------------------------------------------------

class TestCrewAIInvoke:
    async def test_invoke_uses_kickoff_async_when_available(self):
        crew = _crew_mock(has_async=True, result="async result")
        adapter = _adapter_with_obj(crew)
        result = await adapter._invoke(crew, {"input": "data"})
        crew.kickoff_async.assert_awaited_once_with(inputs={"input": "data"})
        assert result == "async result"

    async def test_invoke_falls_back_to_sync_kickoff(self):
        crew = _crew_mock(has_async=False, result="sync result")
        adapter = _adapter_with_obj(crew)
        result = await adapter._invoke(crew, {"input": "data"})
        crew.kickoff.assert_called_once_with(inputs={"input": "data"})
        assert result == "sync result"


# ---------------------------------------------------------------------------
# CrewAIAdapter._extract_output tests
# ---------------------------------------------------------------------------

class TestCrewAIExtractOutput:
    def test_extract_raw_attribute(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        result = MagicMock()
        result.raw = "raw output text"
        assert adapter._extract_output(result) == "raw output text"

    def test_extract_falls_back_to_str(self):
        adapter = CrewAIAdapter("mod.Crew", {})

        class NoRaw:
            def __str__(self):
                return "stringified"

        assert adapter._extract_output(NoRaw()) == "stringified"

    def test_extract_none_output(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        assert adapter._extract_output(None) is None

    def test_crew_output_mock_with_raw(self):
        """Simulate a CrewOutput object that has a .raw attribute."""
        adapter = CrewAIAdapter("mod.Crew", {})

        class CrewOutput:
            raw = "The final answer from the crew"

        output = CrewOutput()
        assert adapter._extract_output(output) == "The final answer from the crew"


# ---------------------------------------------------------------------------
# CrewAIAdapter.execute integration tests
# ---------------------------------------------------------------------------

class TestCrewAIExecute:
    async def test_execute_single_input(self):
        crew = _crew_mock(has_async=True, result="done")
        adapter = _adapter_with_obj(crew)
        task = _make_task()
        arts = [_make_artifact(content="my input")]
        result = await adapter.execute(task, arts, "trace-1")
        assert isinstance(result, ExecutionResult)
        assert result.artifacts[0].content == "done"
        crew.kickoff_async.assert_awaited_once_with(inputs="my input")

    async def test_execute_multiple_inputs(self):
        crew = _crew_mock(has_async=True, result="combined")
        adapter = _adapter_with_obj(crew)
        task = _make_task()
        arts = [_make_artifact(aid="a1", content="c1"), _make_artifact(aid="a2", content="c2")]
        result = await adapter.execute(task, arts, "trace-1")
        assert result.artifacts[0].content == "combined"
        crew.kickoff_async.assert_awaited_once_with(inputs={"a1": "c1", "a2": "c2"})

    async def test_execute_output_dict_becomes_json(self):
        crew = _crew_mock(has_async=True, result={"key": "val"})
        # _extract_output returns str(dict) since MagicMock won't have .raw
        # But we want to test dict normalization, so use a real object
        adapter = _adapter_with_obj(crew)

        # Override _extract_output to return a dict
        adapter._extract_output = lambda r: r if isinstance(r, dict) else str(r)

        task = _make_task()
        result = await adapter.execute(task, [], "trace-1")
        parsed = json.loads(result.artifacts[0].content)
        assert parsed == {"key": "val"}

    async def test_execute_none_output_becomes_empty_string(self):
        crew = _crew_mock(has_async=True, result=None)
        adapter = _adapter_with_obj(crew)
        task = _make_task()
        result = await adapter.execute(task, [], "trace-1")
        assert result.artifacts[0].content == ""

    async def test_execute_framework_exception_wrapped(self):
        crew = MagicMock()
        crew.kickoff_async = AsyncMock(side_effect=Exception("crew crashed"))
        adapter = _adapter_with_obj(crew)
        task = _make_task()
        with pytest.raises(RuntimeError, match="crewai://"):
            await adapter.execute(task, [], "trace-1")


# ---------------------------------------------------------------------------
# CrewAIAdapter.cancel and health tests
# ---------------------------------------------------------------------------

class TestCrewAICancelAndHealth:
    async def test_cancel_is_noop(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        result = await adapter.cancel("task-1")
        assert result is None

    async def test_health_returns_alive(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        assert await adapter.health() == AgentHealth.ALIVE


# ---------------------------------------------------------------------------
# Lazy load test
# ---------------------------------------------------------------------------

class TestCrewAILazyLoad:
    def test_object_not_loaded_until_execute_called(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        assert adapter._obj is None

    def test_load_object_caches(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        crew = MagicMock()
        crew.kickoff = MagicMock()
        fake_module = MagicMock()
        fake_module.Crew = crew

        with patch("importlib.import_module", return_value=fake_module):
            first = adapter._load_object()
            second = adapter._load_object()
        assert first is second
        assert first is crew


# ---------------------------------------------------------------------------
# Prefix test
# ---------------------------------------------------------------------------

class TestCrewAIPrefix:
    def test_prefix_is_crewai(self):
        adapter = CrewAIAdapter("mod.Crew", {})
        assert adapter._prefix == "crewai"
