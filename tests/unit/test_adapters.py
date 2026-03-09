"""Tests for agent adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.adapters.base import AgentAdapter
from binex.adapters.local import LocalPythonAdapter
from binex.adapters.llm import LLMAdapter
from binex.adapters.a2a import A2AAgentAdapter
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


def _make_task(**kwargs) -> TaskNode:
    defaults = {
        "id": "task-1",
        "run_id": "run-1",
        "node_id": "node-1",
        "agent": "local://echo",
    }
    defaults.update(kwargs)
    return TaskNode(**defaults)


def _make_artifact(id: str = "art-1", **kwargs) -> Artifact:
    defaults = {
        "id": id,
        "run_id": "run-1",
        "type": "text",
        "content": "hello",
        "lineage": Lineage(produced_by="node-0"),
    }
    defaults.update(kwargs)
    return Artifact(**defaults)


# --- LocalPythonAdapter ---


@pytest.mark.asyncio
async def test_local_adapter_execute() -> None:
    async def handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        return [
            Artifact(
                id="out-1",
                run_id=task.run_id,
                type="result",
                content=f"processed-{inputs[0].content}",
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )
        ]

    adapter = LocalPythonAdapter(handler=handler)
    task = _make_task()
    inputs = [_make_artifact()]
    results = await adapter.execute(task, inputs, "trace-1")
    assert len(results) == 1
    assert results[0].content == "processed-hello"


@pytest.mark.asyncio
async def test_local_adapter_multiple_outputs() -> None:
    async def handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        return [
            Artifact(id="out-1", run_id=task.run_id, type="a", content="1", lineage=Lineage(produced_by=task.node_id)),
            Artifact(id="out-2", run_id=task.run_id, type="b", content="2", lineage=Lineage(produced_by=task.node_id)),
        ]

    adapter = LocalPythonAdapter(handler=handler)
    results = await adapter.execute(_make_task(), [], "trace-1")
    assert len(results) == 2


@pytest.mark.asyncio
async def test_local_adapter_cancel() -> None:
    adapter = LocalPythonAdapter(handler=AsyncMock())
    await adapter.cancel("task-1")  # Should not raise


@pytest.mark.asyncio
async def test_local_adapter_health() -> None:
    adapter = LocalPythonAdapter(handler=AsyncMock())
    assert await adapter.health() == AgentHealth.ALIVE


# --- LLMAdapter ---


@pytest.mark.asyncio
async def test_llm_adapter_execute() -> None:
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "LLM response text"

    adapter = LLMAdapter(model="gpt-4")
    task = _make_task(system_prompt="summarize")
    inputs = [_make_artifact(content="input data")]

    with patch("binex.adapters.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response):
        results = await adapter.execute(task, inputs, "trace-1")

    assert len(results) == 1
    assert results[0].content == "LLM response text"
    assert results[0].type == "llm_response"


@pytest.mark.asyncio
async def test_llm_adapter_with_config_params() -> None:
    """LLMAdapter forwards optional config params to litellm.acompletion."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "response"

    adapter = LLMAdapter(
        model="gpt-4o",
        api_base="http://proxy:4000",
        api_key="sk-test",
        temperature=0.3,
        max_tokens=1024,
    )
    task = _make_task(system_prompt="plan")

    with patch("binex.adapters.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_llm:
        await adapter.execute(task, [], "trace-1")

    call_kwargs = mock_llm.call_args[1]
    assert call_kwargs["model"] == "gpt-4o"
    assert call_kwargs["api_base"] == "http://proxy:4000"
    assert call_kwargs["api_key"] == "sk-test"
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["max_tokens"] == 1024


@pytest.mark.asyncio
async def test_llm_adapter_without_optional_params() -> None:
    """LLMAdapter omits None params from litellm.acompletion call."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "response"

    adapter = LLMAdapter(model="gpt-4")
    task = _make_task(system_prompt="test")

    with patch("binex.adapters.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_response) as mock_llm:
        await adapter.execute(task, [], "trace-1")

    call_kwargs = mock_llm.call_args[1]
    assert call_kwargs["model"] == "gpt-4"
    assert "api_base" not in call_kwargs
    assert "api_key" not in call_kwargs
    assert "temperature" not in call_kwargs
    assert "max_tokens" not in call_kwargs


@pytest.mark.asyncio
async def test_llm_adapter_health() -> None:
    adapter = LLMAdapter(model="gpt-4")
    assert await adapter.health() == AgentHealth.ALIVE


# --- A2AAgentAdapter ---


@pytest.mark.asyncio
async def test_a2a_adapter_execute() -> None:
    adapter = A2AAgentAdapter(endpoint="http://localhost:9001")
    task = _make_task(system_prompt="research")
    inputs = [_make_artifact(content="query data")]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "artifacts": [
            {"type": "result", "content": "agent output"},
        ]
    }

    with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        results = await adapter.execute(task, inputs, "trace-1")

    assert len(results) == 1
    assert results[0].content == "agent output"


@pytest.mark.asyncio
async def test_a2a_adapter_health_alive() -> None:
    adapter = A2AAgentAdapter(endpoint="http://localhost:9001")

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        health = await adapter.health()

    assert health == AgentHealth.ALIVE


@pytest.mark.asyncio
async def test_a2a_adapter_health_down() -> None:
    adapter = A2AAgentAdapter(endpoint="http://localhost:9001")

    with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_client

        health = await adapter.health()

    assert health == AgentHealth.DOWN


@pytest.mark.asyncio
async def test_a2a_adapter_cancel() -> None:
    adapter = A2AAgentAdapter(endpoint="http://localhost:9001")

    with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
        mock_client_cls.return_value = mock_client

        await adapter.cancel("task-1")  # Should not raise
