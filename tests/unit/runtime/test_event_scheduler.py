"""Event-driven scheduling: a slow node must not block independent ready nodes.

Under the old batch-barrier loop, all nodes in a batch were awaited together, so
a fast node whose dependency finished early still waited for the slowest node in
the batch. These tests pin the event-driven behaviour.
"""

from __future__ import annotations

import asyncio

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _two_chain_workflow() -> dict:
    """Two independent chains: fast1->fast2 and slow1->slow2."""
    return {
        "name": "two-chains",
        "nodes": {
            "fast1": {"agent": "local://work", "inputs": {}, "outputs": ["r"]},
            "fast2": {"agent": "local://work", "inputs": {"x": "${fast1.r}"},
                      "outputs": ["r"], "depends_on": ["fast1"]},
            "slow1": {"agent": "local://work", "inputs": {}, "outputs": ["r"]},
            "slow2": {"agent": "local://work", "inputs": {"x": "${slow1.r}"},
                      "outputs": ["r"], "depends_on": ["slow1"]},
        },
    }


@pytest.mark.asyncio
async def test_fast_branch_not_blocked_by_slow_node():
    completion_order: list[str] = []

    async def handler(task, inputs):
        # slow1 takes far longer than the whole fast chain.
        await asyncio.sleep(0.15 if task.node_id == "slow1" else 0.01)
        completion_order.append(task.node_id)
        return [Artifact(
            id=f"art_{task.node_id}_{task.run_id}", run_id=task.run_id,
            type="r", content={"ok": True},
            lineage=Lineage(produced_by=task.node_id),
        )]

    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    orch.dispatcher.register_adapter("local://work", LocalPythonAdapter(handler=handler))

    summary = await orch.run_workflow(_two_chain_workflow())

    assert summary.status == "completed"
    assert summary.completed_nodes == 4
    # The event-driven scheduler dispatches fast2 as soon as fast1 finishes,
    # so the entire fast chain completes before the slow node — no batch barrier.
    assert completion_order.index("fast2") < completion_order.index("slow1")


@pytest.mark.asyncio
async def test_all_ready_entry_nodes_run_together():
    """Independent entry nodes are dispatched concurrently, not one batch at a time."""
    active = 0
    peak = 0

    async def handler(task, inputs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return [Artifact(
            id=f"art_{task.node_id}_{task.run_id}", run_id=task.run_id,
            type="r", content={}, lineage=Lineage(produced_by=task.node_id),
        )]

    workflow = {
        "name": "fanout",
        "nodes": {
            f"n{i}": {"agent": "local://work", "inputs": {}, "outputs": ["r"]}
            for i in range(4)
        },
    }
    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    orch.dispatcher.register_adapter("local://work", LocalPythonAdapter(handler=handler))

    summary = await orch.run_workflow(workflow)

    assert summary.status == "completed"
    assert peak >= 2  # ran concurrently (default cap is 8, well above 4)
