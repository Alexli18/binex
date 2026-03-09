"""Tests for multi-provider LLM support: config parsing, adapter registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.a2a import A2AAgentAdapter
from binex.adapters.llm import LLMAdapter
from binex.models.workflow import NodeSpec, WorkflowSpec


class TestNodeSpecConfig:
    def test_config_default_empty(self) -> None:
        ns = NodeSpec(agent="llm://gpt-4o", outputs=["out"])
        assert ns.config == {}

    def test_config_with_values(self) -> None:
        ns = NodeSpec(
            agent="llm://gpt-4o",
            outputs=["out"],
            config={"temperature": 0.3, "max_tokens": 2048},
        )
        assert ns.config["temperature"] == 0.3
        assert ns.config["max_tokens"] == 2048

    def test_workflow_with_config_parses(self) -> None:
        spec = WorkflowSpec(
            name="test",
            nodes={
                "planner": NodeSpec(
                    agent="llm://gpt-4o",
                    outputs=["plan"],
                    config={"temperature": 0.3},
                ),
                "worker": NodeSpec(
                    agent="a2a://http://localhost:8001",
                    outputs=["result"],
                    depends_on=["planner"],
                ),
            },
        )
        assert spec.nodes["planner"].config["temperature"] == 0.3
        assert spec.nodes["worker"].config == {}


class TestLLMAdapterConfig:
    @pytest.mark.asyncio
    async def test_config_forwarded_to_litellm(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"

        adapter = LLMAdapter(
            model="gpt-4o",
            api_base="http://proxy:4000",
            api_key="sk-test",
            temperature=0.3,
            max_tokens=1024,
        )

        from binex.models.artifact import Artifact, Lineage
        from binex.models.task import TaskNode

        task = TaskNode(id="t1", run_id="r1", node_id="n1", agent="llm://gpt-4o", system_prompt="test")

        with patch("binex.adapters.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock:
            await adapter.execute(task, [], "trace-1")

        kwargs = mock.call_args[1]
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["api_base"] == "http://proxy:4000"
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["temperature"] == 0.3
        assert kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_none_params_not_forwarded(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"

        adapter = LLMAdapter(model="ollama/llama3.2")

        from binex.models.artifact import Lineage
        from binex.models.task import TaskNode

        task = TaskNode(id="t1", run_id="r1", node_id="n1", agent="llm://ollama/llama3.2", system_prompt="test")

        with patch("binex.adapters.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock:
            await adapter.execute(task, [], "trace-1")

        kwargs = mock.call_args[1]
        assert "api_base" not in kwargs
        assert "api_key" not in kwargs
        assert "temperature" not in kwargs
        assert "max_tokens" not in kwargs


class TestA2ARegistration:
    def test_a2a_adapter_created_with_endpoint(self) -> None:
        endpoint = "http://localhost:8001"
        adapter = A2AAgentAdapter(endpoint=endpoint)
        assert adapter._endpoint == endpoint

    def test_a2a_endpoint_trailing_slash_stripped(self) -> None:
        adapter = A2AAgentAdapter(endpoint="http://localhost:8001/")
        assert adapter._endpoint == "http://localhost:8001"
