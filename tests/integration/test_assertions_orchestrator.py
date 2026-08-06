"""Integration: node assertions block the node and its dependents (issue #60)."""

from __future__ import annotations

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_handler(text: str):
    async def _handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        return [
            Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=text,
                lineage=Lineage(produced_by=task.node_id, derived_from=[]),
            )
        ]
    return _handler


def _orch(text: str) -> Orchestrator:
    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    orch.dispatcher.register_adapter(
        "local://echo", LocalPythonAdapter(handler=_make_handler(text))
    )
    return orch


@pytest.mark.asyncio
async def test_passing_assertion_completes() -> None:
    orch = _orch("the answer is 42")
    wf = {
        "name": "assert-pass",
        "nodes": {
            "n1": {
                "agent": "local://echo",
                "outputs": ["result"],
                "assertions": [{"contains": "42"}],
            },
        },
    }
    summary = await orch.run_workflow(wf)
    assert summary.status == "completed"
    assert summary.failed_nodes == 0


@pytest.mark.asyncio
async def test_failing_assertion_blocks_node() -> None:
    orch = _orch("no number here")
    wf = {
        "name": "assert-fail",
        "nodes": {
            "n1": {
                "agent": "local://echo",
                "outputs": ["result"],
                "assertions": [{"contains": "42"}],
            },
        },
    }
    summary = await orch.run_workflow(wf)
    assert summary.status != "completed"
    assert summary.failed_nodes == 1

    records = await orch.execution_store.list_records(summary.run_id)
    errors = [r.error for r in records if r.error]
    assert any("assertion failed" in e for e in errors)


@pytest.mark.asyncio
async def test_failing_assertion_blocks_dependents() -> None:
    orch = _orch("bad output")
    wf = {
        "name": "assert-blocks-downstream",
        "nodes": {
            "n1": {
                "agent": "local://echo",
                "outputs": ["result"],
                "assertions": [{"contains": "GOOD"}],
            },
            "n2": {
                "agent": "local://echo",
                "outputs": ["final"],
                "depends_on": ["n1"],
            },
        },
    }
    summary = await orch.run_workflow(wf)
    assert summary.status != "completed"
    # n1 failed; n2 must not have completed.
    assert summary.completed_nodes == 0
