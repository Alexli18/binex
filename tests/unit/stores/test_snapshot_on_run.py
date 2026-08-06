"""Test that orchestrator stores workflow snapshot on run."""

from unittest.mock import AsyncMock

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
async def test_run_stores_workflow_snapshot():
    """run_workflow should set workflow_hash on RunSummary."""
    store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    orch = Orchestrator(art_store, store)
    orch.dispatcher.register_adapter("local://echo", _mock_adapter())

    spec = WorkflowSpec(
        name="snap-test",
        nodes={"a": NodeSpec(agent="local://echo", outputs=["out"])},
    )
    summary = await orch.run_workflow(spec)
    assert summary.workflow_hash is not None
    assert len(summary.workflow_hash) == 64
