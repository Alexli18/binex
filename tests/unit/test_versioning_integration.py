"""Integration test — full workflow versioning lifecycle."""

from unittest.mock import AsyncMock

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore
from binex.stores.backends.sqlite import SqliteExecutionStore


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
async def test_full_versioning_lifecycle(tmp_path):
    """Run workflow, verify snapshot stored and retrievable."""
    db_path = str(tmp_path / "test.db")
    store = SqliteExecutionStore(db_path)
    await store.initialize()
    art_store = InMemoryArtifactStore()

    try:
        orch = Orchestrator(art_store, store)
        orch.dispatcher.register_adapter("local://echo", _mock_adapter())

        spec = WorkflowSpec(
            name="versioned",
            version=1,
            nodes={"a": NodeSpec(agent="local://echo", outputs=["out"])},
        )
        summary = await orch.run_workflow(spec)

        # Verify snapshot stored
        assert summary.workflow_hash is not None
        snapshot = await store.get_workflow_snapshot(summary.workflow_hash)
        assert snapshot is not None
        assert "versioned" in snapshot["content"]
        assert snapshot["version"] == 1

        # Run again — same spec should produce same hash
        summary2 = await orch.run_workflow(spec)
        assert summary2.workflow_hash == summary.workflow_hash
    finally:
        await store.close()
