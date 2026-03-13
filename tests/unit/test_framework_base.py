"""Tests for BaseFrameworkAdapter — shared logic for all framework adapters."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(task_id: str = "t1", run_id: str = "run-1", node_id: str = "n1") -> TaskNode:
    return TaskNode(id=task_id, run_id=run_id, node_id=node_id, agent="test://mod.obj")


def _make_artifact(
    aid: str = "a1", run_id: str = "run-1", content: str = "hello",
) -> Artifact:
    return Artifact(
        id=aid, run_id=run_id, type="text", content=content,
        lineage=Lineage(produced_by="prev"),
    )


# ---------------------------------------------------------------------------
# Tests for _load_object (lazy import via importlib)
# ---------------------------------------------------------------------------

class TestLoadObject:
    def test_splits_dotted_path_and_imports(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        adapter = ConcreteAdapter("mypackage.mymodule.MyClass", {})
        fake_obj = MagicMock()
        fake_module = MagicMock()
        fake_module.MyClass = fake_obj

        with patch("importlib.import_module", return_value=fake_module) as mock_import:
            result = adapter._load_object()
            mock_import.assert_called_once_with("mypackage.mymodule")
            assert result is fake_obj

    def test_caches_result_on_second_call(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        adapter = ConcreteAdapter("mod.Cls", {})
        fake_module = MagicMock()
        fake_module.Cls = MagicMock()

        with patch("importlib.import_module", return_value=fake_module) as mock_import:
            first = adapter._load_object()
            second = adapter._load_object()
            assert first is second
            mock_import.assert_called_once()

    def test_import_error_wrapped_with_prefix_and_hint(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        adapter = ConcreteAdapter("nonexistent.module.Obj", {})

        with patch("importlib.import_module", side_effect=ImportError("No module")):
            with pytest.raises(RuntimeError, match="test://"):
                adapter._load_object()

    def test_missing_attribute_raises_error(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        adapter = ConcreteAdapter("mod.Missing", {})
        fake_module = MagicMock(spec=[])  # no attributes

        with patch("importlib.import_module", return_value=fake_module):
            with pytest.raises(RuntimeError, match="Missing"):
                adapter._load_object()


# ---------------------------------------------------------------------------
# Tests for _prepare_input
# ---------------------------------------------------------------------------

class TestPrepareInput:
    def _make_adapter(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        return ConcreteAdapter("mod.Cls", {})

    def test_zero_artifacts_returns_empty_dict(self):
        adapter = self._make_adapter()
        assert adapter._prepare_input([]) == {}

    def test_one_artifact_returns_content(self):
        adapter = self._make_adapter()
        art = _make_artifact(content="hello world")
        assert adapter._prepare_input([art]) == "hello world"

    def test_multiple_artifacts_returns_dict(self):
        adapter = self._make_adapter()
        a1 = _make_artifact(aid="x", content="c1")
        a2 = _make_artifact(aid="y", content="c2")
        result = adapter._prepare_input([a1, a2])
        assert result == {"x": "c1", "y": "c2"}


# ---------------------------------------------------------------------------
# Tests for _normalize_output
# ---------------------------------------------------------------------------

class TestNormalizeOutput:
    def _make_adapter(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        return ConcreteAdapter("mod.Cls", {})

    def test_str_passthrough(self):
        adapter = self._make_adapter()
        assert adapter._normalize_output("hello") == "hello"

    def test_dict_to_json(self):
        adapter = self._make_adapter()
        result = adapter._normalize_output({"key": "val"})
        assert json.loads(result) == {"key": "val"}

    def test_none_to_empty_string(self):
        adapter = self._make_adapter()
        assert adapter._normalize_output(None) == ""

    def test_other_to_str(self):
        adapter = self._make_adapter()
        assert adapter._normalize_output(42) == "42"


# ---------------------------------------------------------------------------
# Tests for _build_result
# ---------------------------------------------------------------------------

class TestBuildResult:
    def _make_adapter(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        return ConcreteAdapter("mod.Cls", {})

    def test_creates_execution_result_with_artifact_and_lineage(self):
        adapter = self._make_adapter()
        task = _make_task()
        inputs = [_make_artifact(aid="in1")]
        result = adapter._build_result(task, inputs, "output content")

        assert isinstance(result, ExecutionResult)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "output content"
        assert result.artifacts[0].lineage.produced_by == "n1"
        assert result.artifacts[0].lineage.derived_from == ["in1"]
        assert result.cost is None


# ---------------------------------------------------------------------------
# Tests for cancel() and health()
# ---------------------------------------------------------------------------

class TestCancelAndHealth:
    def _make_adapter(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class ConcreteAdapter(BaseFrameworkAdapter):
            _prefix = "test"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                pass

            def _extract_output(self, result):
                return str(result)

        return ConcreteAdapter("mod.Cls", {})

    async def test_cancel_is_noop(self):
        adapter = self._make_adapter()
        result = await adapter.cancel("some-id")
        assert result is None

    async def test_health_returns_alive(self):
        adapter = self._make_adapter()
        assert await adapter.health() == AgentHealth.ALIVE


# ---------------------------------------------------------------------------
# Tests for validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_object_missing_required_method_raises(self):
        from binex.adapters.framework_base import BaseFrameworkAdapter

        class StrictAdapter(BaseFrameworkAdapter):
            _prefix = "strict"

            async def _invoke(self, obj, input_data):
                return "ok"

            def _validate(self, obj):
                if not hasattr(obj, "run"):
                    raise ValueError("Object must have 'run' method")

            def _extract_output(self, result):
                return str(result)

        adapter = StrictAdapter("mod.Cls", {})
        fake_module = MagicMock()
        fake_module.Cls = MagicMock(spec=[])  # no 'run' attribute

        with patch("importlib.import_module", return_value=fake_module):
            with pytest.raises(ValueError, match="run"):
                adapter._load_object()
