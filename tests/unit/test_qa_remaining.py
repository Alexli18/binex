"""QA P2/P3 tests — models, DAG, adapters, stores, runtime, workflow spec, CLI, security."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from binex.adapters.llm import LLMAdapter
from binex.adapters.local import LocalPythonAdapter
from binex.graph.dag import DAG
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import RetryPolicy, TaskNode, TaskStatus
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.dispatcher import Dispatcher, _backoff_delay
from binex.stores import create_execution_store
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.workflow_spec.loader import load_workflow_from_string


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(nodes: dict) -> WorkflowSpec:
    return WorkflowSpec(name="test", nodes=nodes)


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
# TC-MOD-002: WorkflowSpec with duplicate node IDs — last-wins behavior
# ---------------------------------------------------------------------------

class TestWorkflowSpecDuplicateNodeIds:
    """Python dicts use last-wins for duplicate keys; verify WorkflowSpec reflects that."""

    def test_dict_duplicate_keys_last_wins_in_yaml(self) -> None:
        """When YAML has duplicate keys, PyYAML keeps the last value."""
        yaml_content = """\
name: test-dupes
nodes:
  step1:
    agent: llm://gpt-4
    outputs: [first_output]
  step1:
    agent: llm://gpt-3.5
    outputs: [second_output]
"""
        spec = load_workflow_from_string(yaml_content, fmt="yaml")

        # Assert — last definition wins
        assert len(spec.nodes) == 1
        assert "step1" in spec.nodes
        assert spec.nodes["step1"].agent == "llm://gpt-3.5"
        assert spec.nodes["step1"].outputs == ["second_output"]

    def test_programmatic_dict_only_has_one_entry(self) -> None:
        """Python dict literals with duplicate keys keep the last value."""
        # Python syntax: duplicate keys in dict literal -> last wins
        nodes = {"a": {"agent": "x", "outputs": ["o1"]}}
        nodes["a"] = {"agent": "y", "outputs": ["o2"]}
        spec = _make_spec(nodes)

        assert len(spec.nodes) == 1
        assert spec.nodes["a"].agent == "y"


# ---------------------------------------------------------------------------
# TC-MOD-005: ExecutionRecord JSON roundtrip
# ---------------------------------------------------------------------------

class TestExecutionRecordJsonRoundtrip:
    """Serialize ExecutionRecord to JSON, deserialize, verify equality."""

    def test_roundtrip_all_fields(self) -> None:
        # Arrange
        record = ExecutionRecord(
            id="exec_1",
            run_id="run_1",
            task_id="task_1",
            parent_task_id="parent_1",
            agent_id="llm://gpt-4",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=["art_in_1"],
            output_artifact_refs=["art_out_1"],
            prompt="What is 2+2?",
            model="gpt-4",
            tool_calls=[{"name": "calc", "args": {"expr": "2+2"}}],
            latency_ms=150,
            trace_id="trace_1",
            error=None,
        )

        # Act
        json_data = record.model_dump(mode="json")
        restored = ExecutionRecord.model_validate(json_data)

        # Assert
        assert restored.id == record.id
        assert restored.run_id == record.run_id
        assert restored.task_id == record.task_id
        assert restored.parent_task_id == record.parent_task_id
        assert restored.agent_id == record.agent_id
        assert restored.status == record.status
        assert restored.input_artifact_refs == record.input_artifact_refs
        assert restored.output_artifact_refs == record.output_artifact_refs
        assert restored.prompt == record.prompt
        assert restored.model == record.model
        assert restored.tool_calls == record.tool_calls
        assert restored.latency_ms == record.latency_ms
        assert restored.trace_id == record.trace_id
        assert restored.error == record.error

    def test_roundtrip_with_error_field(self) -> None:
        """Roundtrip preserves error message."""
        record = ExecutionRecord(
            id="exec_2",
            run_id="run_1",
            task_id="task_2",
            agent_id="llm://gpt-4",
            status=TaskStatus.FAILED,
            latency_ms=50,
            trace_id="trace_1",
            error="Connection reset by peer",
        )

        json_data = record.model_dump(mode="json")
        restored = ExecutionRecord.model_validate(json_data)

        assert restored.error == "Connection reset by peer"
        assert restored.status == TaskStatus.FAILED

    def test_roundtrip_minimal_fields(self) -> None:
        """Roundtrip with only required fields (optional fields use defaults)."""
        record = ExecutionRecord(
            id="exec_3",
            run_id="run_1",
            task_id="task_3",
            agent_id="local://echo",
            status=TaskStatus.COMPLETED,
            latency_ms=10,
            trace_id="trace_1",
        )

        json_data = record.model_dump(mode="json")
        restored = ExecutionRecord.model_validate(json_data)

        assert restored.parent_task_id is None
        assert restored.prompt is None
        assert restored.model is None
        assert restored.tool_calls is None
        assert restored.error is None
        assert restored.input_artifact_refs == []
        assert restored.output_artifact_refs == []


# ---------------------------------------------------------------------------
# TC-MOD-006: RunSummary with completed_nodes > total_nodes
# ---------------------------------------------------------------------------

class TestRunSummaryLogicalInconsistency:
    """Pydantic accepts completed_nodes > total_nodes — no validation constraint."""

    def test_completed_exceeds_total_accepted(self) -> None:
        # Arrange & Act — no validation error expected
        summary = RunSummary(
            run_id="run_1",
            workflow_name="test",
            status="completed",
            total_nodes=3,
            completed_nodes=5,
        )

        # Assert — model allows logically inconsistent values
        assert summary.completed_nodes == 5
        assert summary.total_nodes == 3
        assert summary.completed_nodes > summary.total_nodes

    def test_failed_exceeds_total_accepted(self) -> None:
        summary = RunSummary(
            run_id="run_2",
            workflow_name="test",
            status="failed",
            total_nodes=2,
            failed_nodes=10,
        )

        assert summary.failed_nodes == 10
        assert summary.total_nodes == 2


# ---------------------------------------------------------------------------
# TC-DAG-002: DAG with isolated nodes (no edges, multiple entry points)
# ---------------------------------------------------------------------------

class TestDAGIsolatedNodes:
    """All nodes without dependencies should be entry nodes."""

    def test_all_isolated_nodes_are_entry_nodes(self) -> None:
        # Arrange
        spec = _make_spec({
            "a": {"agent": "x", "outputs": ["o"]},
            "b": {"agent": "x", "outputs": ["o"]},
            "c": {"agent": "x", "outputs": ["o"]},
        })

        # Act
        dag = DAG.from_workflow(spec)

        # Assert
        assert set(dag.entry_nodes()) == {"a", "b", "c"}
        assert len(dag.entry_nodes()) == 3

    def test_isolated_nodes_topological_order_contains_all(self) -> None:
        spec = _make_spec({
            "x": {"agent": "a", "outputs": ["o"]},
            "y": {"agent": "a", "outputs": ["o"]},
            "z": {"agent": "a", "outputs": ["o"]},
        })

        dag = DAG.from_workflow(spec)
        order = dag.topological_order()

        assert set(order) == {"x", "y", "z"}
        assert len(order) == 3

    def test_isolated_nodes_have_no_dependencies(self) -> None:
        spec = _make_spec({
            "a": {"agent": "x", "outputs": ["o"]},
            "b": {"agent": "x", "outputs": ["o"]},
        })

        dag = DAG.from_workflow(spec)

        assert dag.dependencies("a") == set()
        assert dag.dependencies("b") == set()
        assert dag.dependents("a") == set()
        assert dag.dependents("b") == set()


# ---------------------------------------------------------------------------
# TC-DAG-005: Large DAG (50+ nodes) — correctness and no hangs
# ---------------------------------------------------------------------------

class TestLargeDAG:
    """Verify DAG handles 50+ nodes correctly without hanging."""

    def test_large_linear_chain(self) -> None:
        """50-node linear chain: node_0 -> node_1 -> ... -> node_49."""
        # Arrange
        nodes = {}
        for i in range(50):
            node_def: dict = {"agent": "x", "outputs": ["o"]}
            if i > 0:
                node_def["depends_on"] = [f"node_{i - 1}"]
            nodes[f"node_{i}"] = node_def
        spec = _make_spec(nodes)

        # Act
        dag = DAG.from_workflow(spec)
        order = dag.topological_order()

        # Assert
        assert len(order) == 50
        assert dag.entry_nodes() == ["node_0"]
        for i in range(49):
            assert order.index(f"node_{i}") < order.index(f"node_{i + 1}")

    def test_large_fan_out(self) -> None:
        """1 root node with 50 dependents — all dependents are independent."""
        nodes = {"root": {"agent": "x", "outputs": ["o"]}}
        for i in range(50):
            nodes[f"leaf_{i}"] = {
                "agent": "x",
                "outputs": ["o"],
                "depends_on": ["root"],
            }
        spec = _make_spec(nodes)

        dag = DAG.from_workflow(spec)
        order = dag.topological_order()

        assert len(order) == 51
        assert dag.entry_nodes() == ["root"]
        assert order[0] == "root"
        # All leaves come after root
        for i in range(50):
            assert f"leaf_{i}" in order[1:]

    def test_large_diamond_layers(self) -> None:
        """Multi-layer diamond: 5 layers of 10 nodes each, all depending on previous layer."""
        nodes = {}
        for layer in range(5):
            for n in range(10):
                node_id = f"L{layer}_N{n}"
                node_def: dict = {"agent": "x", "outputs": ["o"]}
                if layer > 0:
                    node_def["depends_on"] = [
                        f"L{layer - 1}_N{m}" for m in range(10)
                    ]
                nodes[node_id] = node_def
        spec = _make_spec(nodes)

        dag = DAG.from_workflow(spec)
        order = dag.topological_order()

        assert len(order) == 50
        # All layer 0 nodes should be entry nodes
        entry = dag.entry_nodes()
        assert len(entry) == 10
        for n in range(10):
            assert f"L0_N{n}" in entry


# ---------------------------------------------------------------------------
# TC-ADP-002: LLMAdapter forwards config params to litellm
# ---------------------------------------------------------------------------

class TestLLMAdapterForwardsConfig:
    """Verify api_base, temperature, max_tokens are forwarded to litellm.acompletion."""

    @pytest.mark.asyncio
    async def test_all_config_params_forwarded(self) -> None:
        # Arrange
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"

        adapter = LLMAdapter(
            model="gpt-4o",
            api_base="http://localhost:4000",
            temperature=0.7,
            max_tokens=2048,
        )
        task = _make_task(system_prompt="summarize")

        # Act
        with patch(
            "binex.adapters.llm.litellm.acompletion",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_llm:
            await adapter.execute(task, [], "trace_1")

        # Assert
        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs["api_base"] == "http://localhost:4000"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 2048

    @pytest.mark.asyncio
    async def test_none_params_omitted(self) -> None:
        """When config params are None, they should not appear in the call."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"

        adapter = LLMAdapter(model="gpt-4")
        task = _make_task(system_prompt="test")

        with patch(
            "binex.adapters.llm.litellm.acompletion",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_llm:
            await adapter.execute(task, [], "trace_1")

        call_kwargs = mock_llm.call_args[1]
        assert "api_base" not in call_kwargs
        assert "temperature" not in call_kwargs
        assert "max_tokens" not in call_kwargs
        assert "api_key" not in call_kwargs

    @pytest.mark.asyncio
    async def test_partial_config_only_set_params_forwarded(self) -> None:
        """Only non-None params should be forwarded."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"

        adapter = LLMAdapter(model="gpt-4", temperature=0.5)
        task = _make_task()

        with patch(
            "binex.adapters.llm.litellm.acompletion",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_llm:
            await adapter.execute(task, [], "trace_1")

        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert "api_base" not in call_kwargs
        assert "max_tokens" not in call_kwargs


# ---------------------------------------------------------------------------
# TC-ADP-006: Adapter cancel() on already-completed task — no-op
# ---------------------------------------------------------------------------

class TestAdapterCancelAlreadyCompleted:
    """cancel() should be a no-op on all adapters; no error even if task is done."""

    @pytest.mark.asyncio
    async def test_llm_adapter_cancel_no_op(self) -> None:
        adapter = LLMAdapter(model="gpt-4")

        # Act — cancel a task that doesn't exist or already completed
        result = await adapter.cancel("already-done-task")

        # Assert — no exception, returns None
        assert result is None

    @pytest.mark.asyncio
    async def test_local_adapter_cancel_no_op(self) -> None:
        async def handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            return []

        adapter = LocalPythonAdapter(handler=handler)

        result = await adapter.cancel("already-done-task")

        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_multiple_times_no_error(self) -> None:
        """Calling cancel() multiple times should not raise."""
        adapter = LLMAdapter(model="gpt-4")

        await adapter.cancel("task_1")
        await adapter.cancel("task_1")
        await adapter.cancel("task_1")
        # No exception raised — pass


# ---------------------------------------------------------------------------
# TC-STO-004: FilesystemArtifactStore concurrent store() same artifact_id
# ---------------------------------------------------------------------------

class TestFilesystemStoreConcurrentWrite:
    """Concurrent store() calls with the same artifact_id — last write wins."""

    @pytest.mark.asyncio
    async def test_concurrent_store_same_id_last_write_wins(self) -> None:
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            artifacts = [
                Artifact(
                    id="art_race",
                    run_id="run_1",
                    type="text",
                    content=f"version_{i}",
                    lineage=Lineage(produced_by="node_0"),
                )
                for i in range(5)
            ]

            # Act — store all concurrently
            await asyncio.gather(*(store.store(a) for a in artifacts))

            # Assert — file exists and contains one of the versions
            result = await store.get("art_race")
            assert result is not None
            assert result.id == "art_race"
            # Content should be one of the versions (last write wins, order not guaranteed)
            assert result.content in [f"version_{i}" for i in range(5)]

    @pytest.mark.asyncio
    async def test_sequential_store_overwrites(self) -> None:
        """Sequential stores with the same ID overwrite the previous value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)

            for i in range(3):
                art = Artifact(
                    id="art_overwrite",
                    run_id="run_1",
                    type="text",
                    content=f"v{i}",
                    lineage=Lineage(produced_by="node_0"),
                )
                await store.store(art)

            result = await store.get("art_overwrite")
            assert result is not None
            assert result.content == "v2"


# ---------------------------------------------------------------------------
# TC-STO-006: Factory create_execution_store with unknown backend
# ---------------------------------------------------------------------------

class TestFactoryUnknownBackend:
    """create_execution_store with an unknown backend name raises ValueError."""

    def test_unknown_execution_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown execution store backend: redis"):
            create_execution_store("redis")

    def test_unknown_execution_backend_empty_string(self) -> None:
        with pytest.raises(ValueError, match="Unknown execution store backend: "):
            create_execution_store("")

    def test_unknown_execution_backend_typo(self) -> None:
        with pytest.raises(ValueError, match="Unknown execution store backend: sqllite"):
            create_execution_store("sqllite")


# ---------------------------------------------------------------------------
# TC-RUN-003: Dispatcher retry with exponential backoff
# ---------------------------------------------------------------------------

class TestDispatcherRetryExponentialBackoff:
    """Verify attempt count and delay pattern for exponential backoff."""

    @pytest.mark.asyncio
    async def test_three_retries_exponential_delays(self) -> None:
        """With max_retries=3, adapter is called 3 times with exponential sleep."""
        # Arrange
        call_count = 0

        async def failing_execute(task, inputs, trace_id):
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"fail_{call_count}")

        adapter = MagicMock()
        adapter.execute = failing_execute

        dispatcher = Dispatcher()
        dispatcher.register_adapter("agent", adapter)

        task = _make_task(
            agent="agent",
            retry_policy=RetryPolicy(max_retries=3, backoff="exponential"),
        )

        # Act
        with patch(
            "binex.runtime.dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            with pytest.raises(RuntimeError, match="fail_3"):
                await dispatcher.dispatch(task, [], "trace_1")

        # Assert — 3 attempts, 2 sleeps (between attempts)
        assert call_count == 3
        assert mock_sleep.await_count == 2

        # Verify exponential delay values: attempt 1 -> 0.1, attempt 2 -> 0.2
        sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
        assert sleep_calls[0] == pytest.approx(0.1)  # 2^0 * 0.1
        assert sleep_calls[1] == pytest.approx(0.2)  # 2^1 * 0.1

    @pytest.mark.asyncio
    async def test_success_on_last_retry_no_exception(self) -> None:
        """If the last retry succeeds, result is returned, no exception raised."""
        attempt = 0

        async def flaky_execute(task, inputs, trace_id):
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise RuntimeError("transient")
            return [_make_artifact()]

        adapter = MagicMock()
        adapter.execute = flaky_execute

        dispatcher = Dispatcher()
        dispatcher.register_adapter("agent", adapter)

        task = _make_task(
            agent="agent",
            retry_policy=RetryPolicy(max_retries=3, backoff="exponential"),
        )

        with patch(
            "binex.runtime.dispatcher.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await dispatcher.dispatch(task, [], "trace_1")

        assert len(result.artifacts) == 1
        assert attempt == 3

    def test_backoff_delay_exponential_values(self) -> None:
        """Verify _backoff_delay returns correct exponential values."""
        assert _backoff_delay(1, "exponential") == pytest.approx(0.1)
        assert _backoff_delay(2, "exponential") == pytest.approx(0.2)
        assert _backoff_delay(3, "exponential") == pytest.approx(0.4)
        assert _backoff_delay(4, "exponential") == pytest.approx(0.8)

    def test_backoff_delay_exponential_capped(self) -> None:
        """Exponential backoff is capped at 10.0 seconds."""
        assert _backoff_delay(100, "exponential") == 10.0
        assert _backoff_delay(200, "exponential") == 10.0


# ---------------------------------------------------------------------------
# TC-WFS-001: Workflow with unknown/extra fields — Pydantic behavior
# ---------------------------------------------------------------------------

class TestWorkflowExtraFields:
    """By default Pydantic ignores extra fields (no strict mode configured)."""

    def test_extra_top_level_field_ignored(self) -> None:
        """Extra fields at workflow level should be silently ignored."""
        yaml_content = """\
name: test-extra
description: has extra fields
custom_tag: "2.0"
author: alice
nodes:
  step1:
    agent: llm://gpt-4
    outputs: [result]
"""
        spec = load_workflow_from_string(yaml_content, fmt="yaml")

        assert spec.name == "test-extra"
        assert "step1" in spec.nodes
        # Extra fields not accessible as attributes
        assert not hasattr(spec, "custom_tag")
        assert not hasattr(spec, "author")

    def test_extra_node_field_ignored(self) -> None:
        """Extra fields inside a node definition should be silently ignored."""
        yaml_content = """\
name: test-extra-node
nodes:
  step1:
    agent: llm://gpt-4
    outputs: [result]
    priority: high
    custom_tag: foo
"""
        spec = load_workflow_from_string(yaml_content, fmt="yaml")

        assert spec.nodes["step1"].agent == "llm://gpt-4"
        assert not hasattr(spec.nodes["step1"], "priority")

    def test_missing_required_field_raises(self) -> None:
        """Missing required fields (name, nodes) should raise ValueError."""
        yaml_content = """\
description: no name or nodes
"""
        with pytest.raises(ValueError, match="Invalid workflow spec"):
            load_workflow_from_string(yaml_content, fmt="yaml")


# ---------------------------------------------------------------------------
# TC-WFS-004: Nested ${node.x.y} interpolation — expected behavior
# ---------------------------------------------------------------------------

class TestNestedNodeInterpolation:
    """${node.x.y} references are runtime artifact refs — loader does not resolve them."""

    def test_nested_node_ref_preserved_in_inputs(self) -> None:
        """Nested ${node.x.y} references are kept as-is after loading."""
        yaml_content = """\
name: test-nested-ref
nodes:
  producer:
    agent: llm://gpt-4
    outputs: [data]
  consumer:
    agent: llm://gpt-4
    inputs:
      source: "${producer.data}"
      nested: "${producer.data.summary}"
    outputs: [result]
    depends_on: [producer]
"""
        spec = load_workflow_from_string(yaml_content, fmt="yaml")

        # Both references are preserved as literal strings (runtime resolves them)
        assert spec.nodes["consumer"].inputs["source"] == "${producer.data}"
        assert spec.nodes["consumer"].inputs["nested"] == "${producer.data.summary}"

    def test_user_var_resolved_node_ref_preserved(self) -> None:
        """${user.*} is resolved at load time; ${node.*} is preserved."""
        yaml_content = """\
name: test-mixed-ref
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      query: "${user.topic}"
      context: "${step0.output}"
    outputs: [result]
"""
        spec = load_workflow_from_string(
            yaml_content,
            fmt="yaml",
            user_vars={"topic": "quantum computing"},
        )

        assert spec.nodes["step1"].inputs["query"] == "quantum computing"
        assert spec.nodes["step1"].inputs["context"] == "${step0.output}"

    def test_llm_adapter_skips_nested_node_refs_in_prompt(self) -> None:
        """LLMAdapter._build_prompt skips inputs with ${...} including nested refs."""
        adapter = LLMAdapter(model="m")
        task = _make_task(
            system_prompt="analyze",
            inputs={
                "data": "${node_a.output.summary}",
                "format": "json",
            },
        )

        prompt = adapter._build_prompt(task, [])

        assert "${node_a.output.summary}" not in prompt
        assert "format: json" in prompt


# ---------------------------------------------------------------------------
# TC-CLI-005: binex debug --rich without rich installed — graceful fallback
# ---------------------------------------------------------------------------

class TestDebugRichFallback:
    """When --rich is used but rich is not installed, CLI should exit with error message."""

    def test_rich_import_error_exits_cleanly(self) -> None:
        """Simulate ImportError on 'from binex.trace.debug_rich import ...'."""
        from click.testing import CliRunner
        from binex.cli.debug import debug_cmd

        runner = CliRunner()

        # Mock stores to return a valid report
        mock_exec_store = AsyncMock()
        mock_exec_store.close = AsyncMock()
        mock_art_store = MagicMock()

        with patch("binex.cli.debug._get_stores", return_value=(mock_exec_store, mock_art_store)):
            with patch(
                "binex.cli.debug.build_debug_report",
                new_callable=AsyncMock,
                return_value=MagicMock(),  # non-None report
            ):
                with patch(
                    "binex.trace.debug_rich.format_debug_report_rich",
                    side_effect=ImportError("No module named 'rich'"),
                ):
                    # The import happens inside _debug_async; simulate the ImportError
                    # by patching the import itself
                    import builtins
                    original_import = builtins.__import__

                    def mock_import(name, *args, **kwargs):
                        if name == "binex.trace.debug_rich":
                            raise ImportError("No module named 'rich'")
                        return original_import(name, *args, **kwargs)

                    with patch("builtins.__import__", side_effect=mock_import):
                        result = runner.invoke(debug_cmd, ["run_123", "--rich"])

                    # Now falls back to plain text gracefully
                    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TC-SEC-006: Error messages don't expose internal file paths
# ---------------------------------------------------------------------------

class TestErrorMessagesNoInternalPaths:
    """Verify that user-facing errors don't leak internal filesystem paths."""

    def test_unknown_node_dependency_error_no_path(self) -> None:
        """DAG error for unknown dependency should mention node names, not file paths."""
        spec = _make_spec({
            "a": {"agent": "x", "outputs": ["o"], "depends_on": ["nonexistent"]},
        })

        with pytest.raises(ValueError, match="nonexistent") as exc_info:
            DAG.from_workflow(spec)

        error_msg = str(exc_info.value)
        # Should not contain filesystem paths
        assert "/Users/" not in error_msg
        assert "/home/" not in error_msg
        assert "\\Users\\" not in error_msg
        assert ".py" not in error_msg

    def test_invalid_workflow_yaml_error_no_path(self) -> None:
        """Invalid workflow YAML error should not expose loader file paths."""
        yaml_content = """\
name: 123
nodes: not_a_dict
"""
        with pytest.raises(ValueError, match="Invalid workflow spec") as exc_info:
            load_workflow_from_string(yaml_content, fmt="yaml")

        error_msg = str(exc_info.value)
        assert "/Users/" not in error_msg
        assert "/home/" not in error_msg

    def test_filesystem_store_path_traversal_error_no_leak(self) -> None:
        """FilesystemArtifactStore path traversal error should not expose base_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)

            with pytest.raises(ValueError, match="Invalid path component") as exc_info:
                art = Artifact(
                    id="../../etc/passwd",
                    run_id="run_1",
                    type="text",
                    content="malicious",
                    lineage=Lineage(produced_by="node_0"),
                )
                asyncio.run(store.store(art))

            error_msg = str(exc_info.value)
            # Error mentions the bad component but not the base path
            assert tmpdir not in error_msg

    def test_store_factory_error_no_path_leak(self) -> None:
        """Factory ValueError should not contain filesystem paths."""
        with pytest.raises(ValueError, match="Unknown execution store backend") as exc_info:
            create_execution_store("bogus")

        error_msg = str(exc_info.value)
        assert "/Users/" not in error_msg
        assert "/home/" not in error_msg
        assert ".py" not in error_msg
