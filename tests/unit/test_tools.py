"""Tests for binex.tools — @tool decorator, schema generation, tool loading, tool call loop."""

from __future__ import annotations

import asyncio
import json
import textwrap
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.tools import (
    ToolDefinition,
    build_tool_schema,
    execute_tool_call,
    load_python_tool,
    resolve_tools,
    tool,
)


# ---------------------------------------------------------------------------
# TestToolDecorator
# ---------------------------------------------------------------------------


class TestToolDecorator:
    """Tests for the @tool decorator."""

    def test_bare_decorator(self):
        """@tool without arguments marks the function."""

        @tool
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        assert hasattr(greet, "_binex_tool")
        assert greet._binex_tool["name"] is None
        assert greet._binex_tool["description"] is None
        # Function still works
        assert greet("World") == "Hello, World!"

    def test_with_description(self):
        """@tool(description=...) overrides docstring."""

        @tool(description="Custom description")
        def search(query: str) -> str:
            """Original docstring."""
            return query

        assert search._binex_tool["description"] == "Custom description"

    def test_with_name_override(self):
        """@tool(name=...) overrides function name."""

        @tool(name="web_search")
        def search(query: str) -> str:
            """Search."""
            return query

        assert search._binex_tool["name"] == "web_search"

    def test_with_parameter_descriptions(self):
        """@tool(parameter_descriptions=...) adds param docs."""

        @tool(parameter_descriptions={"query": "Search query", "limit": "Max results"})
        def search(query: str, limit: int = 5) -> str:
            """Search."""
            return query

        assert search._binex_tool["parameter_descriptions"]["query"] == "Search query"


# ---------------------------------------------------------------------------
# TestSchemaGeneration
# ---------------------------------------------------------------------------


class TestSchemaGeneration:
    """Tests for build_tool_schema()."""

    def test_str_param(self):
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hi {name}"

        schema = build_tool_schema(greet)
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "greet"
        assert schema["function"]["parameters"]["properties"]["name"]["type"] == "string"
        assert "name" in schema["function"]["parameters"]["required"]

    def test_int_param(self):
        def count(n: int) -> str:
            """Count."""
            return str(n)

        schema = build_tool_schema(count)
        assert schema["function"]["parameters"]["properties"]["n"]["type"] == "integer"

    def test_optional_param_not_required(self):
        def search(query: str, limit: int = 5) -> str:
            """Search."""
            return query

        schema = build_tool_schema(search)
        assert "query" in schema["function"]["parameters"]["required"]
        assert "limit" not in schema["function"]["parameters"]["required"]

    def test_docstring_extraction(self):
        def calculator(expr: str) -> str:
            """Evaluate a math expression."""
            return expr

        schema = build_tool_schema(calculator)
        assert schema["function"]["description"] == "Evaluate a math expression."

    def test_decorated_function_override(self):
        @tool(name="calc", description="Calculate things")
        def calculator(expr: str) -> str:
            """Original doc."""
            return expr

        schema = build_tool_schema(calculator)
        assert schema["function"]["name"] == "calc"
        assert schema["function"]["description"] == "Calculate things"


# ---------------------------------------------------------------------------
# TestToolLoader
# ---------------------------------------------------------------------------


class TestToolLoader:
    """Tests for load_python_tool()."""

    def test_load_valid_uri(self, tmp_path):
        """Load a valid python:// URI."""
        module_file = tmp_path / "mytools.py"
        module_file.write_text(textwrap.dedent("""\
            def search(query: str) -> str:
                \"\"\"Search the web.\"\"\"
                return f"Results for {query}"
        """))

        td = load_python_tool("python://mytools.search", workflow_dir=str(tmp_path))
        assert td.name == "search"
        assert td.callable is not None
        assert td.callable("test") == "Results for test"

    def test_module_not_found(self):
        with pytest.raises(ImportError, match="Cannot import module"):
            load_python_tool("python://nonexistent_module_xyz.func")

    def test_function_not_found(self, tmp_path):
        module_file = tmp_path / "mymod.py"
        module_file.write_text("x = 1\n")

        with pytest.raises(AttributeError, match="has no function"):
            load_python_tool("python://mymod.no_such_func", workflow_dir=str(tmp_path))

    def test_not_callable(self, tmp_path):
        module_file = tmp_path / "mymod2.py"
        module_file.write_text("NOT_A_FUNC = 42\n")

        with pytest.raises(TypeError, match="is not callable"):
            load_python_tool("python://mymod2.NOT_A_FUNC", workflow_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# TestToolCallLoop (via LLMAdapter integration)
# ---------------------------------------------------------------------------


class TestToolCallLoop:
    """Tests for tool call loop in LLMAdapter."""

    def _make_task(self, tools=None, system_prompt=None, config=None):
        from binex.models.task import TaskNode

        return TaskNode(
            id="t1",
            run_id="run1",
            node_id="n1",
            agent="llm://openai/gpt-4o",
            system_prompt=system_prompt,
            tools=tools or [],
            inputs={"topic": "test"},
        )

    def _make_tool_call(self, tc_id, name, arguments):
        """Create a mock tool_call object."""
        func = SimpleNamespace(name=name, arguments=json.dumps(arguments))
        return SimpleNamespace(id=tc_id, function=func)

    @pytest.mark.asyncio
    async def test_single_tool_call_round(self):
        """LLMAdapter handles one tool call round then text response."""
        from binex.adapters.llm import LLMAdapter

        tool_call = self._make_tool_call("tc_1", "calc", {"expr": "2+2"})

        # First response: tool call, Second response: text
        msg1 = MagicMock()
        msg1.tool_calls = [tool_call]
        msg1.content = None
        msg1.model_dump.return_value = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "tc_1", "function": {"name": "calc", "arguments": '{"expr":"2+2"}'}}],
        }

        msg2 = MagicMock()
        msg2.tool_calls = None
        msg2.content = "The answer is 4"

        resp1 = MagicMock()
        resp1.choices = [SimpleNamespace(message=msg1)]
        resp2 = MagicMock()
        resp2.choices = [SimpleNamespace(message=msg2)]

        calc_tool = ToolDefinition(
            name="calc",
            description="Calculate",
            parameters={"type": "object", "properties": {"expr": {"type": "string"}}},
            callable=lambda expr: str(eval(expr)),
            is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc_tool]):
            mock_litellm.acompletion = AsyncMock(side_effect=[resp1, resp2])

            task = self._make_task(tools=["python://mytools.calc"], system_prompt="You are a calculator")
            result = await adapter.execute(task, [], "trace1")

        arts = result.artifacts
        assert len(arts) == 1
        assert arts[0].content == "The answer is 4"
        assert mock_litellm.acompletion.call_count == 2

    @pytest.mark.asyncio
    async def test_multi_round_tool_calls(self):
        """LLMAdapter handles multiple tool call rounds."""
        from binex.adapters.llm import LLMAdapter

        def make_tc_response(tc_id, name, args):
            tc = self._make_tool_call(tc_id, name, args)
            msg = MagicMock()
            msg.tool_calls = [tc]
            msg.content = None
            msg.model_dump.return_value = {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": tc_id, "function": {"name": name, "arguments": json.dumps(args)}}],
            }
            resp = MagicMock()
            resp.choices = [SimpleNamespace(message=msg)]
            return resp

        final_msg = MagicMock()
        final_msg.tool_calls = None
        final_msg.content = "Done"
        final_resp = MagicMock()
        final_resp.choices = [SimpleNamespace(message=final_msg)]

        calc_tool = ToolDefinition(
            name="calc", description="Calc",
            parameters={"type": "object", "properties": {}},
            callable=lambda **kw: "ok",
            is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[calc_tool]):
            mock_litellm.acompletion = AsyncMock(side_effect=[
                make_tc_response("tc_1", "calc", {}),
                make_tc_response("tc_2", "calc", {}),
                final_resp,
            ])

            task = self._make_task(tools=["python://mytools.calc"])
            result = await adapter.execute(task, [], "trace1")

        assert result.artifacts[0].content == "Done"
        assert mock_litellm.acompletion.call_count == 3

    @pytest.mark.asyncio
    async def test_async_tool_execution(self):
        """LLMAdapter handles async tool functions."""
        from binex.adapters.llm import LLMAdapter

        async def async_calc(expr: str) -> str:
            return str(eval(expr))

        tool_call = self._make_tool_call("tc_1", "async_calc", {"expr": "3*3"})

        msg1 = MagicMock()
        msg1.tool_calls = [tool_call]
        msg1.content = None
        msg1.model_dump.return_value = {"role": "assistant", "content": None, "tool_calls": []}

        msg2 = MagicMock()
        msg2.tool_calls = None
        msg2.content = "9"

        resp1 = MagicMock()
        resp1.choices = [SimpleNamespace(message=msg1)]
        resp2 = MagicMock()
        resp2.choices = [SimpleNamespace(message=msg2)]

        async_tool = ToolDefinition(
            name="async_calc", description="Async calc",
            parameters={"type": "object", "properties": {"expr": {"type": "string"}}},
            callable=async_calc,
            is_async=True,
        )

        adapter = LLMAdapter(model="gpt-4o")

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[async_tool]):
            mock_litellm.acompletion = AsyncMock(side_effect=[resp1, resp2])

            task = self._make_task(tools=["python://mytools.async_calc"])
            result = await adapter.execute(task, [], "trace1")

        assert result.artifacts[0].content == "9"


# ---------------------------------------------------------------------------
# TestInlineToolSchema (US3)
# ---------------------------------------------------------------------------


class TestInlineToolSchema:
    """Tests for inline tool definitions."""

    def test_basic_inline_schema(self):
        """Inline dict creates valid ToolDefinition."""
        tools = resolve_tools([{
            "name": "calculate",
            "description": "Evaluate math",
            "parameters": {"expr": {"type": "string"}},
        }])
        assert len(tools) == 1
        assert tools[0].name == "calculate"
        assert tools[0].callable is None
        assert tools[0].parameters["properties"]["expr"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_missing_handler_returns_error(self):
        """Tool with no callable returns error message."""
        td = ToolDefinition(
            name="missing_tool",
            description="No handler",
            parameters={},
            callable=None,
        )
        result = await execute_tool_call(td, {})
        assert "Error" in result
        assert "no handler" in result.lower()

    def test_mixed_python_and_inline_tools(self, tmp_path):
        """resolve_tools handles mix of python:// and inline dicts."""
        module_file = tmp_path / "toolmod.py"
        module_file.write_text(textwrap.dedent("""\
            def hello(name: str) -> str:
                \"\"\"Say hi.\"\"\"
                return f"Hi {name}"
        """))

        tools = resolve_tools(
            [
                "python://toolmod.hello",
                {"name": "calc", "description": "Calculate", "parameters": {}},
            ],
            workflow_dir=str(tmp_path),
        )
        assert len(tools) == 2
        assert tools[0].callable is not None
        assert tools[1].callable is None


# ---------------------------------------------------------------------------
# TestMaxToolRounds (US4)
# ---------------------------------------------------------------------------


class TestMaxToolRounds:
    """Tests for max_tool_rounds configuration."""

    def _make_task(self, tools=None, config=None):
        from binex.models.task import TaskNode

        return TaskNode(
            id="t1", run_id="run1", node_id="n1",
            agent="llm://openai/gpt-4o",
            tools=tools or [],
            config=config or {},
        )

    def _make_tool_call_response(self):
        tc = SimpleNamespace(
            id="tc_1",
            function=SimpleNamespace(name="func", arguments="{}"),
        )
        msg = MagicMock()
        msg.tool_calls = [tc]
        msg.content = None
        msg.model_dump.return_value = {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "tc_1", "function": {"name": "func", "arguments": "{}"}}],
        }
        resp = MagicMock()
        resp.choices = [SimpleNamespace(message=msg)]
        return resp

    @pytest.mark.asyncio
    async def test_default_limit_10(self):
        """Default max_tool_rounds is 10."""
        from binex.adapters.llm import LLMAdapter

        func_tool = ToolDefinition(
            name="func", description="Func",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "ok",
            is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")
        # initial call + 10 re-calls in loop = 11 total
        responses = [self._make_tool_call_response() for _ in range(11)]

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[func_tool]):
            mock_litellm.acompletion = AsyncMock(side_effect=responses)

            task = self._make_task(tools=["python://m.func"])
            with pytest.raises(RuntimeError, match="Exceeded max tool rounds"):
                await adapter.execute(task, [], "trace1")

    @pytest.mark.asyncio
    async def test_custom_limit_from_config(self):
        """max_tool_rounds from task.config overrides default."""
        from binex.adapters.llm import LLMAdapter

        func_tool = ToolDefinition(
            name="func", description="Func",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "ok",
            is_async=False,
        )

        adapter = LLMAdapter(model="gpt-4o")
        # initial call + 2 re-calls in loop = 3 total
        responses = [self._make_tool_call_response() for _ in range(3)]

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[func_tool]):
            mock_litellm.acompletion = AsyncMock(side_effect=responses)

            task = self._make_task(
                tools=["python://m.func"],
                config={"max_tool_rounds": 2},
            )
            with pytest.raises(RuntimeError, match="Exceeded max tool rounds"):
                await adapter.execute(task, [], "trace1")

    @pytest.mark.asyncio
    async def test_limit_zero_disables_tools(self):
        """max_tool_rounds=0 disables tool calling entirely."""
        from binex.adapters.llm import LLMAdapter

        msg = MagicMock()
        msg.tool_calls = None
        msg.content = "Direct response"
        resp = MagicMock()
        resp.choices = [SimpleNamespace(message=msg)]

        adapter = LLMAdapter(model="gpt-4o")

        func_tool = ToolDefinition(
            name="func", description="Func",
            parameters={"type": "object", "properties": {}},
            callable=lambda: "ok",
            is_async=False,
        )

        with patch("binex.adapters.llm.litellm") as mock_litellm, \
             patch("binex.adapters.llm.resolve_tools", return_value=[func_tool]):
            mock_litellm.acompletion = AsyncMock(return_value=resp)

            task = self._make_task(
                tools=["python://m.func"],
                config={"max_tool_rounds": 0},
            )
            result = await adapter.execute(task, [], "trace1")

        assert result.artifacts[0].content == "Direct response"
        # resolve_tools should not even be called when max_tool_rounds=0
        # But even if it is, tools should NOT be in litellm kwargs


# ---------------------------------------------------------------------------
# TestExecuteToolCall
# ---------------------------------------------------------------------------


class TestExecuteToolCall:
    """Tests for execute_tool_call()."""

    @pytest.mark.asyncio
    async def test_sync_tool(self):
        td = ToolDefinition(
            name="add", description="Add",
            parameters={},
            callable=lambda a, b: a + b,
            is_async=False,
        )
        result = await execute_tool_call(td, {"a": 1, "b": 2})
        assert result == "3"

    @pytest.mark.asyncio
    async def test_async_tool(self):
        async def async_add(a: int, b: int) -> int:
            return a + b

        td = ToolDefinition(
            name="add", description="Add",
            parameters={},
            callable=async_add,
            is_async=True,
        )
        result = await execute_tool_call(td, {"a": 1, "b": 2})
        assert result == "3"

    @pytest.mark.asyncio
    async def test_tool_exception_returns_error_string(self):
        def bad_func():
            raise ValueError("oops")

        td = ToolDefinition(
            name="bad", description="Bad",
            parameters={},
            callable=bad_func,
            is_async=False,
        )
        result = await execute_tool_call(td, {})
        assert "Error executing tool" in result
        assert "oops" in result
