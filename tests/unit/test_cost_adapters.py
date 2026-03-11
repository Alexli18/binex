"""Tests for adapter cost extraction — LLM, A2A, Local, Human adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord, ExecutionResult
from binex.models.task import TaskNode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(node_id: str = "test_node", agent: str = "llm://gpt-4") -> TaskNode:
    return TaskNode(
        id=f"run_test_{node_id}",
        run_id="run_test",
        node_id=node_id,
        agent=agent,
        system_prompt=None,
        tools=[],
        inputs={},
    )


def _make_llm_response(
    content: str = "test response",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> MagicMock:
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    choice = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_input_artifact() -> Artifact:
    return Artifact(
        id="art_input_001",
        run_id="run_test",
        type="text",
        content="input data",
        lineage=Lineage(produced_by="upstream_node"),
    )


# ---------------------------------------------------------------------------
# LLMAdapter cost extraction
# ---------------------------------------------------------------------------


class TestLLMAdapterCost:
    """LLMAdapter cost extraction from litellm responses."""

    @pytest.mark.asyncio
    async def test_cost_with_usage_data(self) -> None:
        """Mock litellm response with usage data — CostRecord should have tokens and cost."""
        from binex.adapters.llm import LLMAdapter

        response = _make_llm_response(prompt_tokens=100, completion_tokens=50)
        task = _make_task()

        with (
            patch("binex.adapters.llm.litellm") as mock_litellm,
        ):
            mock_litellm.acompletion = AsyncMock(return_value=response)
            mock_litellm.completion_cost.return_value = 0.0045

            adapter = LLMAdapter(model="gpt-4")
            result = await adapter.execute(task, [_make_input_artifact()], "trace_1")

        assert isinstance(result, ExecutionResult)
        assert result.cost is not None

        cost = result.cost
        assert isinstance(cost, CostRecord)
        assert cost.run_id == "run_test"
        assert cost.task_id == "test_node"
        assert cost.cost == 0.0045
        assert cost.source == "llm_tokens"
        assert cost.prompt_tokens == 100
        assert cost.completion_tokens == 50
        assert cost.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_cost_without_usage_data(self) -> None:
        """litellm response WITHOUT usage — cost=0, source='llm_tokens_unavailable'."""
        from binex.adapters.llm import LLMAdapter

        response = _make_llm_response()
        response.usage = None  # No usage data

        task = _make_task()

        with patch("binex.adapters.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=response)

            adapter = LLMAdapter(model="gpt-4")
            result = await adapter.execute(task, [], "trace_2")

        cost = result.cost
        assert cost is not None
        assert cost.cost == 0.0
        assert cost.source == "llm_tokens_unavailable"
        assert cost.prompt_tokens is None
        assert cost.completion_tokens is None

    @pytest.mark.asyncio
    async def test_completion_cost_raises_exception(self) -> None:
        """litellm.completion_cost raises — cost=0, source='llm_tokens_unavailable'."""
        from binex.adapters.llm import LLMAdapter

        response = _make_llm_response(prompt_tokens=200, completion_tokens=80)
        task = _make_task()

        with patch("binex.adapters.llm.litellm") as mock_litellm:
            mock_litellm.acompletion = AsyncMock(return_value=response)
            mock_litellm.completion_cost.side_effect = Exception("Unknown model")

            adapter = LLMAdapter(model="custom-model")
            result = await adapter.execute(task, [], "trace_3")

        cost = result.cost
        assert cost is not None
        assert cost.cost == 0.0
        assert cost.source == "llm_tokens_unavailable"
        # Tokens are still extracted even though cost calculation failed
        assert cost.prompt_tokens == 200
        assert cost.completion_tokens == 80
        assert cost.model == "custom-model"


# ---------------------------------------------------------------------------
# A2AAgentAdapter cost extraction
# ---------------------------------------------------------------------------


class TestA2AAdapterCost:
    """A2AAgentAdapter cost extraction from HTTP responses."""

    @pytest.mark.asyncio
    async def test_response_with_cost(self) -> None:
        """Response WITH cost field — recorded with source='agent_report'."""
        from binex.adapters.a2a import A2AAgentAdapter

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"type": "result", "content": "test output"}],
            "cost": 0.12,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        task = _make_task(agent="a2a://http://localhost:8000")

        with patch("binex.adapters.a2a.httpx.AsyncClient", return_value=mock_client):
            adapter = A2AAgentAdapter(endpoint="http://localhost:8000")
            result = await adapter.execute(task, [], "trace_4")

        assert result.cost is not None
        assert result.cost.cost == 0.12
        assert result.cost.source == "agent_report"
        assert result.cost.run_id == "run_test"
        assert result.cost.task_id == "test_node"

    @pytest.mark.asyncio
    async def test_response_without_cost(self) -> None:
        """Response WITHOUT cost field — cost=0, source='unknown'."""
        from binex.adapters.a2a import A2AAgentAdapter

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"type": "result", "content": "done"}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        task = _make_task(agent="a2a://http://localhost:8000")

        with patch("binex.adapters.a2a.httpx.AsyncClient", return_value=mock_client):
            adapter = A2AAgentAdapter(endpoint="http://localhost:8000")
            result = await adapter.execute(task, [], "trace_5")

        assert result.cost is not None
        assert result.cost.cost == 0.0
        assert result.cost.source == "unknown"


# ---------------------------------------------------------------------------
# LocalPythonAdapter cost extraction
# ---------------------------------------------------------------------------


class TestLocalPythonAdapterCost:
    """LocalPythonAdapter always returns cost=0, source='local'."""

    @pytest.mark.asyncio
    async def test_local_adapter_cost(self) -> None:
        from binex.adapters.local import LocalPythonAdapter

        async def handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            return [
                Artifact(
                    id="art_local_001",
                    run_id=task.run_id,
                    type="result",
                    content="local result",
                    lineage=Lineage(produced_by=task.node_id),
                )
            ]

        task = _make_task(agent="local://handler")
        adapter = LocalPythonAdapter(handler=handler)
        result = await adapter.execute(task, [], "trace_6")

        assert isinstance(result, ExecutionResult)
        assert result.cost is None


# ---------------------------------------------------------------------------
# Human adapters cost extraction
# ---------------------------------------------------------------------------


class TestHumanApprovalAdapterCost:
    """HumanApprovalAdapter returns cost=0, source='local'."""

    @pytest.mark.asyncio
    async def test_approval_adapter_cost(self) -> None:
        from binex.adapters.human import HumanApprovalAdapter

        task = _make_task(agent="human://approval")

        with patch("binex.adapters.human.click.prompt", return_value="y"):
            adapter = HumanApprovalAdapter()
            result = await adapter.execute(task, [_make_input_artifact()], "trace_7")

        assert result.cost is None
        # Verify artifacts are still produced
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "approved"


class TestHumanInputAdapterCost:
    """HumanInputAdapter returns cost=0, source='local'."""

    @pytest.mark.asyncio
    async def test_input_adapter_cost(self) -> None:
        from binex.adapters.human import HumanInputAdapter

        task = _make_task(agent="human://input")

        with patch("binex.adapters.human.click.prompt", return_value="user text"):
            adapter = HumanInputAdapter()
            result = await adapter.execute(task, [], "trace_8")

        assert result.cost is None
        # Verify artifacts are still produced
        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "user text"
