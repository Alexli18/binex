"""Tests for LocalShellAdapter — real shell execution via local:// URI."""

from __future__ import annotations

import json

import pytest

from binex.adapters.local import LocalShellAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


def _make_task(node_id: str = "node1", run_id: str = "run1") -> TaskNode:
    return TaskNode(
        id=f"{run_id}_{node_id}",
        run_id=run_id,
        node_id=node_id,
        agent=f"local://{node_id}",
        system_prompt=None,
        tools=[],
        inputs={},
        retry_policy=None,
        deadline_ms=None,
        config={},
    )


def _make_artifact(art_id: str = "a1", content: str = "hello") -> Artifact:
    return Artifact(
        id=art_id,
        run_id="run1",
        type="result",
        content=content,
        lineage=Lineage(produced_by="prev"),
    )


class TestLocalShellAdapterBasic:
    """Basic shell command execution."""

    @pytest.mark.asyncio
    async def test_echo_command(self):
        adapter = LocalShellAdapter(command="echo hello world")
        result = await adapter.execute(_make_task(), [], "trace1")
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "hello world"

    @pytest.mark.asyncio
    async def test_json_output_parsed(self):
        adapter = LocalShellAdapter(command='echo \'{"key": "value"}\'')
        result = await adapter.execute(_make_task(), [], "trace1")
        assert result.artifacts[0].content == {"key": "value"}

    @pytest.mark.asyncio
    async def test_non_json_output_as_string(self):
        adapter = LocalShellAdapter(command="echo plain text")
        result = await adapter.execute(_make_task(), [], "trace1")
        assert result.artifacts[0].content == "plain text"

    @pytest.mark.asyncio
    async def test_artifact_metadata(self):
        task = _make_task(node_id="mynode", run_id="run42")
        adapter = LocalShellAdapter(command="echo ok")
        result = await adapter.execute(task, [], "trace1")
        art = result.artifacts[0]
        assert art.id == "art_mynode"
        assert art.run_id == "run42"
        assert art.type == "result"
        assert art.lineage.produced_by == "mynode"

    @pytest.mark.asyncio
    async def test_derived_from_inputs(self):
        inputs = [_make_artifact("inp1"), _make_artifact("inp2")]
        adapter = LocalShellAdapter(command="echo ok")
        result = await adapter.execute(_make_task(), inputs, "trace1")
        assert result.artifacts[0].lineage.derived_from == ["inp1", "inp2"]


class TestLocalShellAdapterInput:
    """BINEX_INPUT environment variable passing."""

    @pytest.mark.asyncio
    async def test_binex_input_env_var(self):
        adapter = LocalShellAdapter(command="echo $BINEX_INPUT")
        inputs = [_make_artifact("a1", "data1")]
        result = await adapter.execute(_make_task(), inputs, "trace1")
        # stdout should contain the JSON-encoded input
        output = result.artifacts[0].content
        if isinstance(output, str):
            parsed = json.loads(output)
        else:
            parsed = output
        assert parsed == {"a1": "data1"}

    @pytest.mark.asyncio
    async def test_empty_input_gives_empty_dict(self):
        adapter = LocalShellAdapter(command="echo $BINEX_INPUT")
        result = await adapter.execute(_make_task(), [], "trace1")
        output = result.artifacts[0].content
        if isinstance(output, str):
            parsed = json.loads(output)
        else:
            parsed = output
        assert parsed == {}


class TestLocalShellAdapterErrors:
    """Error handling: non-zero exit, timeout."""

    @pytest.mark.asyncio
    async def test_nonzero_exit_raises(self):
        adapter = LocalShellAdapter(command="exit 1")
        with pytest.raises(RuntimeError, match="failed.*exit 1"):
            await adapter.execute(_make_task(), [], "trace1")

    @pytest.mark.asyncio
    async def test_nonzero_exit_includes_stderr(self):
        adapter = LocalShellAdapter(command="echo 'bad stuff' >&2; exit 2")
        with pytest.raises(RuntimeError, match="bad stuff"):
            await adapter.execute(_make_task(), [], "trace1")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        adapter = LocalShellAdapter(command="sleep 10", timeout=1)
        with pytest.raises(RuntimeError, match="timed out"):
            await adapter.execute(_make_task(), [], "trace1")

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        adapter = LocalShellAdapter(command="nonexistent_command_xyz_12345")
        with pytest.raises(RuntimeError, match="failed"):
            await adapter.execute(_make_task(), [], "trace1")


class TestLocalShellAdapterHealth:
    """Health and cancel methods."""

    @pytest.mark.asyncio
    async def test_health_alive(self):
        from binex.models.agent import AgentHealth
        adapter = LocalShellAdapter(command="echo ok")
        assert await adapter.health() == AgentHealth.ALIVE

    @pytest.mark.asyncio
    async def test_cancel_noop(self):
        adapter = LocalShellAdapter(command="echo ok")
        await adapter.cancel("task1")  # should not raise


class TestAdapterRegistryRouting:
    """Verify adapter_registry routes local:// URIs correctly."""

    def test_local_stub_gets_default_handler(self):
        from binex.adapters.local import LocalPythonAdapter
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "local://stub", "outputs": ["o"]}},
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)
        assert isinstance(dispatcher._adapters["local://stub"], LocalPythonAdapter)

    def test_local_echo_gets_default_handler(self):
        from binex.adapters.local import LocalPythonAdapter
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "local://echo", "outputs": ["o"]}},
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)
        assert isinstance(dispatcher._adapters["local://echo"], LocalPythonAdapter)

    def test_local_bare_gets_default_handler(self):
        from binex.adapters.local import LocalPythonAdapter
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "local://", "outputs": ["o"]}},
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)
        assert isinstance(dispatcher._adapters["local://"], LocalPythonAdapter)

    def test_local_command_gets_shell_adapter(self):
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "local://echo hello", "outputs": ["o"]}},
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)
        assert isinstance(
            dispatcher._adapters["local://echo hello"], LocalShellAdapter,
        )

    def test_local_python_script_gets_shell_adapter(self):
        from binex.cli.adapter_registry import register_workflow_adapters
        from binex.models.workflow import WorkflowSpec
        from binex.runtime.dispatcher import Dispatcher

        spec = WorkflowSpec(
            name="test",
            nodes={"a": {"agent": "local://python3 -c 'print(1)'", "outputs": ["o"]}},
        )
        dispatcher = Dispatcher()
        register_workflow_adapters(dispatcher, spec)
        assert isinstance(
            dispatcher._adapters["local://python3 -c 'print(1)'"], LocalShellAdapter,
        )
