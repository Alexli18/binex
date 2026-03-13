"""Integration test — full run with OTEL mocked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


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
async def test_full_run_with_otel_tracing():
    """Complete workflow run should produce run span + node spans."""
    spans_created = []

    class RecordingSpan:
        def __init__(self, name):
            self.name = name
            self.attributes = {}
            spans_created.append(self)

        def set_attribute(self, k, v):
            self.attributes[k] = v

        def set_status(self, s):
            pass

        def record_exception(self, e):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    class RecordingTracer:
        def start_as_current_span(self, name, **kw):
            return RecordingSpan(name)

    with patch("binex.runtime.orchestrator.get_tracer", return_value=RecordingTracer()), \
         patch("binex.runtime.dispatcher.get_tracer", return_value=RecordingTracer()):
        store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        orch = Orchestrator(art_store, store)
        orch.dispatcher.register_adapter("local://echo", _mock_adapter())

        spec = WorkflowSpec(
            name="otel-test",
            nodes={
                "a": NodeSpec(agent="local://echo", outputs=["out"]),
                "b": NodeSpec(agent="local://echo", outputs=["out"], depends_on=["a"]),
            },
        )
        summary = await orch.run_workflow(spec)

    assert summary.status == "completed"
    span_names = [s.name for s in spans_created]
    assert "binex.run" in span_names
    assert "binex.node.a" in span_names
    assert "binex.node.b" in span_names
