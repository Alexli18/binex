"""Tests for OTEL instrumentation in orchestrator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _simple_workflow():
    return WorkflowSpec(
        name="test-wf",
        nodes={
            "a": NodeSpec(agent="local://echo", outputs=["out"]),
        },
    )


def _mock_adapter():
    adapter = AsyncMock()
    adapter.execute.return_value = ExecutionResult(
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
    return adapter


@pytest.mark.asyncio
async def test_run_workflow_creates_otel_span():
    """run_workflow should create a binex.run span with workflow attributes."""
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)

    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_span

    with patch("binex.runtime.orchestrator.get_tracer", return_value=mock_tracer):
        store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, store)
        orch.dispatcher.register_adapter("local://echo", _mock_adapter())

        summary = await orch.run_workflow(_simple_workflow())

    mock_tracer.start_as_current_span.assert_called_once()
    call_args = mock_tracer.start_as_current_span.call_args
    assert call_args[0][0] == "binex.run"
    mock_span.set_attribute.assert_any_call("workflow.name", "test-wf")
    mock_span.set_attribute.assert_any_call("run.id", summary.run_id)
