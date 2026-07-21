"""Integration tests for dynamic fan-out — runtime foreach expansion (#77)."""

from __future__ import annotations

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _mapper(items: list) -> object:
    async def _handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        return [Artifact(
            id=f"art_{task.node_id}", run_id=task.run_id, type="result",
            content=items, lineage=Lineage(produced_by=task.node_id),
        )]
    return _handler


async def _worker(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    item = inputs[0].content if inputs else None
    return [Artifact(
        id=f"art_{task.node_id}", run_id=task.run_id, type="result",
        content={"processed": item},
        lineage=Lineage(produced_by=task.node_id, derived_from=[a.id for a in inputs]),
    )]


async def _failing_worker(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    item = inputs[0].content if inputs else None
    if isinstance(item, dict) and item.get("bad"):
        raise RuntimeError("worker blew up")
    return [Artifact(
        id=f"art_{task.node_id}", run_id=task.run_id, type="result",
        content={"processed": item},
        lineage=Lineage(produced_by=task.node_id, derived_from=[a.id for a in inputs]),
    )]


def _orch(mapper_items: list, worker_handler=_worker) -> Orchestrator:
    orch = Orchestrator(
        artifact_store=InMemoryArtifactStore(),
        execution_store=InMemoryExecutionStore(),
    )
    orch.dispatcher.register_adapter(
        "local://map", LocalPythonAdapter(handler=_mapper(mapper_items)),
    )
    orch.dispatcher.register_adapter("local://work", LocalPythonAdapter(handler=worker_handler))
    return orch


def _wf(extra_work: dict | None = None) -> dict:
    work = {
        "agent": "local://work",
        "outputs": ["out"],
        "foreach": "map",
    }
    work.update(extra_work or {})
    return {
        "name": "foreach-demo",
        "nodes": {
            "map": {"agent": "local://map", "outputs": ["items"]},
            "work": work,
        },
    }


@pytest.mark.asyncio
async def test_foreach_expands_and_aggregates() -> None:
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    orch = _orch(items)
    summary = await orch.run_workflow(_wf())
    assert summary.status == "completed"

    records = await orch.execution_store.list_records(summary.run_id)
    ids = {r.task_id for r in records}
    # mapper + 3 workers + aggregator + the foreach placeholder
    worker_ids = [i for i in ids if i.startswith("work::") and i != "work::aggregate"]
    assert len(worker_ids) == 3
    assert "work::aggregate" in ids

    arts = await orch.artifact_store.list_by_run(summary.run_id)
    agg = next(a for a in arts if a.lineage.produced_by == "work::aggregate")
    assert agg.content["total"] == 3
    assert agg.content["succeeded"] == 3
    assert agg.content["failed"] == []
    assert len(agg.content["results"]) == 3


@pytest.mark.asyncio
async def test_foreach_max_items_guardrail() -> None:
    items = [{"id": i} for i in range(5)]
    orch = _orch(items)
    summary = await orch.run_workflow(_wf({"max_items": 3}))
    assert summary.status != "completed"
    records = await orch.execution_store.list_records(summary.run_id)
    err = next(r.error for r in records if r.task_id == "work" and r.error)
    assert "max_items" in err


@pytest.mark.asyncio
async def test_foreach_on_item_failure_continue() -> None:
    items = [{"id": "a"}, {"id": "b", "bad": True}, {"id": "c"}]
    orch = _orch(items, worker_handler=_failing_worker)
    summary = await orch.run_workflow(_wf({"on_item_failure": "continue"}))
    # The run completes; the aggregator reports the one failure.
    assert summary.status == "completed"
    arts = await orch.artifact_store.list_by_run(summary.run_id)
    agg = next(a for a in arts if a.lineage.produced_by == "work::aggregate")
    assert agg.content["succeeded"] == 2
    assert len(agg.content["failed"]) == 1


@pytest.mark.asyncio
async def test_foreach_fail_fast_blocks_aggregator() -> None:
    items = [{"id": "a"}, {"id": "b", "bad": True}]
    orch = _orch(items, worker_handler=_failing_worker)
    summary = await orch.run_workflow(_wf({"on_item_failure": "fail_fast"}))
    assert summary.status != "completed"
    # Aggregator must not have produced a result.
    arts = await orch.artifact_store.list_by_run(summary.run_id)
    assert not any(a.lineage.produced_by == "work::aggregate" for a in arts)


@pytest.mark.asyncio
async def test_foreach_bad_mapper_output_fails() -> None:
    orch = _orch({"not": "a list"})  # mapper emits a dict, not an array
    summary = await orch.run_workflow(_wf())
    assert summary.status != "completed"
    records = await orch.execution_store.list_records(summary.run_id)
    err = next(r.error for r in records if r.task_id == "work" and r.error)
    assert "array" in err.lower()


@pytest.mark.asyncio
async def test_foreach_downstream_consumes_aggregate() -> None:
    items = [{"id": "a"}, {"id": "b"}]
    orch = _orch(items)
    orch.dispatcher.register_adapter("local://sink", LocalPythonAdapter(handler=_worker))
    wf = _wf()
    wf["nodes"]["sink"] = {
        "agent": "local://sink", "outputs": ["final"], "depends_on": ["work"],
    }
    summary = await orch.run_workflow(wf)
    assert summary.status == "completed"
    records = await orch.execution_store.list_records(summary.run_id)
    # The sink ran (its dependency was rewired from 'work' to the aggregator).
    assert any(r.task_id == "sink" and r.status.value == "completed" for r in records)
