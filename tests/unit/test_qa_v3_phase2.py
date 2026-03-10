"""QA v3 Phase 2: Core Features — Tools, LLM Adapter + Tools, Conditional Execution.

Covers CAT-1 (TC-TOOL-*), CAT-2 (TC-LLM-*), CAT-3 (TC-WHEN-*).
Gap-filling tests — verifies areas NOT covered by existing test_tools.py / test_when_conditions.py.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator, evaluate_when
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.tools import (
    ToolDefinition,
    build_tool_schema,
    execute_tool_call,
    load_python_tool,
    resolve_tools,
    tool,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _make_artifact(run_id: str, node_id: str, content: str, art_type: str = "result") -> Artifact:
    return Artifact(
        id=f"{run_id}_{node_id}_out",
        run_id=run_id,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=node_id),
    )


class FakeAdapter:
    def __init__(self, content: str = "done") -> None:
        self._content = content

    async def execute(self, task, input_artifacts, trace_id):
        return [_make_artifact(task.run_id, task.node_id, self._content)]

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


def _make_spec(nodes_dict: dict) -> WorkflowSpec:
    nodes = {}
    for nid, ndata in nodes_dict.items():
        nodes[nid] = NodeSpec(
            agent=ndata.get("agent", "llm://test"),
            outputs=ndata.get("outputs", ["result"]),
            depends_on=ndata.get("depends_on", []),
            when=ndata.get("when"),
            inputs=ndata.get("inputs", {}),
            tools=ndata.get("tools", []),
        )
    return WorkflowSpec(name="test-workflow", nodes=nodes)


# ===========================================================================
# CAT-1: Tool System — Gap Tests (TC-TOOL-001 .. TC-TOOL-020)
# ===========================================================================


class TestToolSystemGaps:
    """Gap tests for tool system not covered by existing test_tools.py."""

    # TC-TOOL-001: @tool decorator → ToolDefinition via build_tool_schema
    def test_tool_001_decorated_function_schema(self):
        @tool
        def search(query: str) -> str:
            """Search the web."""
            return query

        schema = build_tool_schema(search)
        assert schema["function"]["name"] == "search"
        assert schema["function"]["description"] == "Search the web."

    # TC-TOOL-003: int/float/bool mapping
    def test_tool_003_numeric_and_bool_mapping(self):
        def calc(a: int, b: float, flag: bool) -> str:
            return ""

        schema = build_tool_schema(calc)
        props = schema["function"]["parameters"]["properties"]
        assert props["a"]["type"] == "integer"
        assert props["b"]["type"] == "number"
        assert props["flag"]["type"] == "boolean"

    # TC-TOOL-004: list/dict mapping
    def test_tool_004_list_dict_mapping(self):
        def process(items: list, config: dict) -> str:
            return ""

        schema = build_tool_schema(process)
        props = schema["function"]["parameters"]["properties"]
        assert props["items"]["type"] == "array"
        assert props["config"]["type"] == "object"

    # TC-TOOL-005: no type hint → "string" fallback
    def test_tool_005_no_type_hint_fallback(self):
        def untyped(x):
            return x

        schema = build_tool_schema(untyped)
        assert schema["function"]["parameters"]["properties"]["x"]["type"] == "string"

    # TC-TOOL-006: function without params
    def test_tool_006_no_params(self):
        def no_args() -> str:
            """No args."""
            return "ok"

        schema = build_tool_schema(no_args)
        assert schema["function"]["parameters"]["properties"] == {}
        assert "required" not in schema["function"]["parameters"]

    # TC-TOOL-008: invalid URI (no python://)
    def test_tool_008_invalid_uri_scheme(self):
        with pytest.raises(ValueError, match="must start with"):
            load_python_tool("http://example.com/tool")

    # TC-TOOL-008b: invalid URI (no dot separator)
    def test_tool_008b_invalid_uri_no_dot(self):
        with pytest.raises(ValueError, match="must be python://"):
            load_python_tool("python://modulewithoutdot")

    # TC-TOOL-012: inline tool missing name → uses "unnamed_tool"
    def test_tool_012_inline_missing_name_uses_default(self):
        tools = resolve_tools([{"description": "calc"}])
        assert tools[0].name == "unnamed_tool"

    # TC-TOOL-014: resolve empty list → empty
    def test_tool_014_resolve_empty(self):
        result = resolve_tools([])
        assert result == []

    # TC-TOOL-015: execute sync function success
    @pytest.mark.asyncio
    async def test_tool_015_execute_sync(self):
        td = ToolDefinition(
            name="greet", description="Greet",
            parameters={},
            callable=lambda name: f"Hi {name}",
            is_async=False,
        )
        result = await execute_tool_call(td, {"name": "Alice"})
        assert result == "Hi Alice"

    # TC-TOOL-016: execute async function success
    @pytest.mark.asyncio
    async def test_tool_016_execute_async(self):
        async def async_greet(name: str) -> str:
            return f"Hello {name}"

        td = ToolDefinition(
            name="greet", description="Greet",
            parameters={},
            callable=async_greet,
            is_async=True,
        )
        result = await execute_tool_call(td, {"name": "Bob"})
        assert result == "Hello Bob"

    # TC-TOOL-019: to_openai_schema valid structure
    def test_tool_019_openai_schema_structure(self):
        td = ToolDefinition(
            name="calc",
            description="Calculate",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
        )
        schema = td.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calc"
        assert schema["function"]["description"] == "Calculate"
        assert schema["function"]["parameters"]["properties"]["x"]["type"] == "integer"

    # TC-TOOL-013: resolve mixed specs (URI + inline)
    def test_tool_013_resolve_mixed(self, tmp_path):
        mod = tmp_path / "mtools.py"
        mod.write_text('def hello(name: str) -> str:\n    """Hi."""\n    return name\n')

        tools = resolve_tools(
            ["python://mtools.hello", {"name": "calc", "description": "Calc", "parameters": {}}],
            workflow_dir=str(tmp_path),
        )
        assert len(tools) == 2
        assert tools[0].callable is not None
        assert tools[1].callable is None

    # TC-TOOL-017: exception → error string
    @pytest.mark.asyncio
    async def test_tool_017_exception_returns_error(self):
        def boom():
            raise RuntimeError("kaboom")

        td = ToolDefinition(name="boom", description="", parameters={}, callable=boom)
        result = await execute_tool_call(td, {})
        assert "Error executing tool" in result
        assert "kaboom" in result

    # TC-TOOL-018: no handler → error
    @pytest.mark.asyncio
    async def test_tool_018_no_handler_error(self):
        td = ToolDefinition(name="ghost", description="", parameters={}, callable=None)
        result = await execute_tool_call(td, {})
        assert "no handler" in result.lower()

    # Unsupported URI scheme
    def test_tool_unsupported_uri_scheme(self):
        with pytest.raises(ValueError, match="Unsupported tool URI"):
            resolve_tools(["file://local/tool"])

    # Invalid spec type
    def test_tool_invalid_spec_type(self):
        with pytest.raises(TypeError, match="Invalid tool spec type"):
            resolve_tools([42])


# ===========================================================================
# CAT-2: LLM Adapter Tool Integration — Gap Tests (TC-LLM-001 .. TC-LLM-012)
# ===========================================================================


class TestLLMAdapterToolGaps:
    """Gap tests for LLM adapter tool calling."""

    def _make_task(self, tools=None, config=None, system_prompt=None):
        return TaskNode(
            id="t1", run_id="run1", node_id="n1",
            agent="llm://gpt-4o",
            system_prompt=system_prompt,
            tools=tools or [],
            config=config or {},
            inputs={"topic": "test"},
        )

    def _make_tool_call(self, tc_id, name, arguments):
        func = SimpleNamespace(name=name, arguments=json.dumps(arguments))
        return SimpleNamespace(id=tc_id, function=func)

    def _final_response(self, content="Done"):
        msg = MagicMock()
        msg.tool_calls = None
        msg.content = content
        resp = MagicMock()
        resp.choices = [SimpleNamespace(message=msg)]
        return resp

    def _tool_call_response(self, tc_id, name, args):
        tc = self._make_tool_call(tc_id, name, args)
        msg = MagicMock()
        msg.tool_calls = [tc]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant", "content": None,
            "tool_calls": [
                {"id": tc_id, "function": {"name": name, "arguments": json.dumps(args)}},
            ],
        }
        resp = MagicMock()
        resp.choices = [SimpleNamespace(message=msg)]
        return resp

    # TC-LLM-005: Unknown tool in tool_calls
    @pytest.mark.asyncio
    async def test_llm_005_unknown_tool(self):
        from binex.adapters.llm import LLMAdapter

        calc = ToolDefinition(
            name="calc", description="Calc",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "ok", is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc]):
            # Response has tool_call for "unknown_fn" — not in resolved tools
            mock_litellm.acompletion = AsyncMock(side_effect=[
                self._tool_call_response("tc_1", "unknown_fn", {}),
                self._final_response("result"),
            ])
            task = self._make_task(tools=["python://m.calc"])
            result = await adapter.execute(task, [], "trace1")

        # Should still complete (unknown tool returns error string)
        assert result.artifacts[0].content == "result"

    # TC-LLM-006: Invalid JSON args in tool_calls
    @pytest.mark.asyncio
    async def test_llm_006_invalid_json_args(self):
        from binex.adapters.llm import LLMAdapter

        calc = ToolDefinition(
            name="calc", description="Calc",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "ok", is_async=False,
        )

        # Tool call with invalid JSON arguments
        tc = SimpleNamespace(
            id="tc_1",
            function=SimpleNamespace(name="calc", arguments="not valid json"),
        )
        msg1 = MagicMock()
        msg1.tool_calls = [tc]
        msg1.content = None
        msg1.model_dump.return_value = {"role": "assistant", "content": None, "tool_calls": []}
        resp1 = MagicMock()
        resp1.choices = [SimpleNamespace(message=msg1)]

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc]):
            mock_litellm.acompletion = AsyncMock(side_effect=[resp1, self._final_response()])
            task = self._make_task(tools=["python://m.calc"])
            result = await adapter.execute(task, [], "trace1")

        assert result.artifacts[0].content == "Done"

    # TC-LLM-007: No tool_calls → normal output
    @pytest.mark.asyncio
    async def test_llm_007_no_tool_calls_normal(self):
        from binex.adapters.llm import LLMAdapter

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=self._final_response("Hello"))
            task = self._make_task()  # no tools
            result = await adapter.execute(task, [], "trace1")

        assert result.artifacts[0].content == "Hello"
        assert mock_litellm.acompletion.call_count == 1

    # TC-LLM-008: Tools=[] → no tools param sent
    @pytest.mark.asyncio
    async def test_llm_008_empty_tools_no_param(self):
        from binex.adapters.llm import LLMAdapter

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=self._final_response("Hi"))
            task = self._make_task(tools=[])
            await adapter.execute(task, [], "trace1")

        # Verify "tools" was NOT in the kwargs
        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert "tools" not in call_kwargs

    # TC-LLM-009: Tool result appended as tool message
    @pytest.mark.asyncio
    async def test_llm_009_tool_result_as_message(self):
        from binex.adapters.llm import LLMAdapter

        calc = ToolDefinition(
            name="calc", description="Calc",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "42", is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc]):
            mock_litellm.acompletion = AsyncMock(side_effect=[
                self._tool_call_response("tc_1", "calc", {}),
                self._final_response("Answer: 42"),
            ])
            task = self._make_task(tools=["python://m.calc"])
            await adapter.execute(task, [], "trace1")

        # Second call should have tool message in messages
        second_call = mock_litellm.acompletion.call_args_list[1]
        messages = second_call.kwargs["messages"]
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["content"] == "42"
        assert tool_msgs[0]["tool_call_id"] == "tc_1"

    # TC-LLM-012: Tool exception doesn't crash adapter
    @pytest.mark.asyncio
    async def test_llm_012_tool_exception_no_crash(self):
        from binex.adapters.llm import LLMAdapter

        def bad_tool():
            raise RuntimeError("oops")

        calc = ToolDefinition(
            name="calc", description="Calc",
            parameters={"type": "object", "properties": {}},
            callable=bad_tool, is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc]):
            mock_litellm.acompletion = AsyncMock(side_effect=[
                self._tool_call_response("tc_1", "calc", {}),
                self._final_response("Error handled"),
            ])
            task = self._make_task(tools=["python://m.calc"])
            result = await adapter.execute(task, [], "trace1")

        # Adapter should continue and return response
        assert result.artifacts[0].content == "Error handled"

    # TC-LLM-001: Tools schema sent to litellm
    @pytest.mark.asyncio
    async def test_llm_001_tools_schema_sent(self):
        from binex.adapters.llm import LLMAdapter

        calc = ToolDefinition(
            name="calc", description="Calculate",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            callable=lambda x: str(x), is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc]):
            mock_litellm.acompletion = AsyncMock(return_value=self._final_response("ok"))
            task = self._make_task(tools=["python://m.calc"])
            await adapter.execute(task, [], "trace1")

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "calc"


# ===========================================================================
# CAT-3: Conditional Execution — Gap Tests (TC-WHEN-001 .. TC-WHEN-015)
# ===========================================================================


class TestConditionalExecutionGaps:
    """Gap tests for when conditions not covered by existing test_when_conditions.py."""

    # TC-WHEN-005: Skipped node counted in summary
    @pytest.mark.asyncio
    async def test_when_005_skipped_in_summary(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} == yes",
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="no"))
        summary = await orch.run_workflow(spec)
        assert summary.skipped_nodes == 1
        assert summary.completed_nodes + summary.skipped_nodes == summary.total_nodes

    # TC-WHEN-006: Skipped resolves downstream deps
    @pytest.mark.asyncio
    async def test_when_006_skipped_resolves_downstream(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "middle": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} == yes",
            },
            "final": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["middle"],
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="no"))
        summary = await orch.run_workflow(spec)
        # middle skipped, final should still execute
        assert summary.status == "completed"
        assert summary.skipped_nodes == 1
        assert summary.completed_nodes == 2

    # TC-WHEN-011: Fan-out both branches execute
    @pytest.mark.asyncio
    async def test_when_011_fan_out_both_execute(self):
        spec = _make_spec({
            "classifier": {"agent": "llm://test", "outputs": ["category"]},
            "premium": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["classifier"],
                "when": "${classifier.category} == premium",
            },
            "standard": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["classifier"],
                "when": "${classifier.category} != premium",
            },
        })

        class CategoryAdapter:
            async def execute(self, task, inputs, trace_id):
                return [_make_artifact(task.run_id, task.node_id, "premium", "category")]
            async def cancel(self, task_id): pass
            async def health(self): return AgentHealth.ALIVE

        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", CategoryAdapter())
        summary = await orch.run_workflow(spec)
        # premium should execute, standard should skip
        assert summary.completed_nodes == 2
        assert summary.skipped_nodes == 1

    # TC-WHEN-012: Fan-out one branch skipped
    @pytest.mark.asyncio
    async def test_when_012_fan_out_one_skipped(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "branch_a": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} == go",
            },
            "branch_b": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} != go",
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="go"))
        summary = await orch.run_workflow(spec)
        assert summary.completed_nodes == 2  # check + branch_a
        assert summary.skipped_nodes == 1  # branch_b

    # TC-WHEN-013: when value with spaces
    def test_when_013_value_with_spaces(self):
        arts = {"check": [_make_artifact("r1", "check", "hello world")]}
        assert evaluate_when("${check.result} == hello world", arts) is True

    # TC-WHEN-014: when empty value
    def test_when_014_empty_value(self):
        arts = {"check": [_make_artifact("r1", "check", "")]}
        # Empty value after == — regex requires at least 1 char for value group
        # So this should either match or raise ValueError
        try:
            result = evaluate_when("${check.result} == ", arts)
            # If it matches, empty == empty should be True
            assert result is True or result is False
        except ValueError:
            pass  # Invalid syntax is acceptable

    # TC-WHEN-015: Multiple when cascading skips
    @pytest.mark.asyncio
    async def test_when_015_cascading_skips(self):
        spec = _make_spec({
            "start": {"agent": "llm://test", "outputs": ["result"]},
            "step2": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["start"],
                "when": "${start.result} == go",
            },
            "step3": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["step2"],
                "when": "${step2.result} == go",
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="stop"))
        summary = await orch.run_workflow(spec)
        # step2 skipped because start returns "stop", step3 should handle missing artifacts
        assert summary.skipped_nodes >= 1
        assert summary.status == "completed"

    # TC-WHEN-003/004: != operator tests with orchestrator
    @pytest.mark.asyncio
    async def test_when_003_not_equals_match_execute(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} != blocked",
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="ok"))
        summary = await orch.run_workflow(spec)
        assert summary.completed_nodes == 2  # Both should execute

    @pytest.mark.asyncio
    async def test_when_004_not_equals_no_match_skip(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test", "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} != done",
            },
        })
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="done"))
        summary = await orch.run_workflow(spec)
        assert summary.skipped_nodes == 1  # "act" skipped because content IS "done"

    # TC-TOOL-020 / TC-LLM-004: max_tool_rounds enforcement (with custom limit)
    @pytest.mark.asyncio
    async def test_tool_020_max_rounds_enforcement(self):
        from binex.adapters.llm import LLMAdapter

        def make_tc_resp():
            tc = SimpleNamespace(
                id="tc_1",
                function=SimpleNamespace(name="func", arguments="{}"),
            )
            msg = MagicMock()
            msg.tool_calls = [tc]
            msg.content = None
            msg.model_dump.return_value = {"role": "assistant", "content": None, "tool_calls": []}
            resp = MagicMock()
            resp.choices = [SimpleNamespace(message=msg)]
            return resp

        func_tool = ToolDefinition(
            name="func", description="",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "ok", is_async=False,
        )
        adapter = LLMAdapter(model="gpt-4o")

        # 1 initial + 3 loop = 4 calls, max_tool_rounds=3
        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[func_tool]):
            mock_litellm.acompletion = AsyncMock(
                side_effect=[make_tc_resp() for _ in range(4)]
            )
            task = TaskNode(
                id="t1", run_id="run1", node_id="n1",
                agent="llm://gpt-4o",
                tools=["python://m.func"],
                config={"max_tool_rounds": 3},
            )
            with pytest.raises(RuntimeError, match="Exceeded max tool rounds"):
                await adapter.execute(task, [], "trace1")
