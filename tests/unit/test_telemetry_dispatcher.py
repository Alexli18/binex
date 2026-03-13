"""Tests for OTEL instrumentation in dispatcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode
from binex.runtime.dispatcher import Dispatcher


@pytest.mark.asyncio
async def test_dispatch_creates_node_span():
    """dispatch should create a binex.node.{id} span."""
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_span

    mock_adapter = AsyncMock()
    mock_adapter.execute.return_value = ExecutionResult(
        artifacts=[
            Artifact(
                id="art_1",
                run_id="run_1",
                type="text",
                content="hello",
                lineage=Lineage(produced_by="a"),
            )
        ]
    )

    with patch("binex.runtime.dispatcher.get_tracer", return_value=mock_tracer):
        dispatcher = Dispatcher()
        dispatcher.register_adapter("local://echo", mock_adapter)

        task = TaskNode(
            id="run_1_a",
            run_id="run_1",
            node_id="a",
            agent="local://echo",
            inputs={},
            config={},
        )
        result = await dispatcher.dispatch(task, [], "trace_1")

    mock_tracer.start_as_current_span.assert_called_once()
    call_name = mock_tracer.start_as_current_span.call_args[0][0]
    assert call_name == "binex.node.a"
    mock_span.set_attribute.assert_any_call("node.id", "a")
    mock_span.set_attribute.assert_any_call("node.agent", "local://echo")
