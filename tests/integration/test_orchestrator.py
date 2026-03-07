"""Integration tests for the orchestrator."""

from __future__ import annotations

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


async def _echo_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    content = {a.id: a.content for a in inputs} if inputs else {"msg": "initial"}
    return [
        Artifact(
            id=f"art_{task.node_id}",
            run_id=task.run_id,
            type="result",
            content=content,
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in inputs],
            ),
        )
    ]


async def _failing_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    raise RuntimeError("agent failed")


def _build_orchestrator(
    adapters: dict[str, LocalPythonAdapter] | None = None,
) -> Orchestrator:
    artifact_store = InMemoryArtifactStore()
    execution_store = InMemoryExecutionStore()
    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )
    if adapters:
        for key, adapter in adapters.items():
            orch.dispatcher.register_adapter(key, adapter)
    return orch


@pytest.mark.asyncio
async def test_simple_two_node_workflow() -> None:
    adapter = LocalPythonAdapter(handler=_echo_handler)
    orch = _build_orchestrator({"local://echo": adapter})

    workflow_dict = {
        "name": "test-simple",
        "nodes": {
            "producer": {
                "agent": "local://echo",
                "outputs": ["result"],
            },
            "consumer": {
                "agent": "local://echo",
                "outputs": ["final"],
                "depends_on": ["producer"],
            },
        },
    }

    summary = await orch.run_workflow(workflow_dict)
    assert summary.status == "completed"
    assert summary.completed_nodes == 2
    assert summary.failed_nodes == 0


@pytest.mark.asyncio
async def test_five_node_pipeline() -> None:
    adapter = LocalPythonAdapter(handler=_echo_handler)
    orch = _build_orchestrator({
        "local://planner": adapter,
        "local://researcher": adapter,
        "local://validator": adapter,
        "local://summarizer": adapter,
    })

    workflow_dict = {
        "name": "research-pipeline",
        "nodes": {
            "planner": {
                "agent": "local://planner",
                "outputs": ["execution_plan"],
            },
            "researcher_1": {
                "agent": "local://researcher",
                "outputs": ["search_results"],
                "depends_on": ["planner"],
            },
            "researcher_2": {
                "agent": "local://researcher",
                "outputs": ["search_results"],
                "depends_on": ["planner"],
            },
            "validator": {
                "agent": "local://validator",
                "outputs": ["validated_results"],
                "depends_on": ["researcher_1", "researcher_2"],
            },
            "summarizer": {
                "agent": "local://summarizer",
                "outputs": ["summary_report"],
                "depends_on": ["validator"],
            },
        },
    }

    summary = await orch.run_workflow(workflow_dict)
    assert summary.status == "completed"
    assert summary.completed_nodes == 5
    assert summary.total_nodes == 5


@pytest.mark.asyncio
async def test_workflow_with_failing_node() -> None:
    echo_adapter = LocalPythonAdapter(handler=_echo_handler)
    fail_adapter = LocalPythonAdapter(handler=_failing_handler)

    orch = _build_orchestrator({
        "local://echo": echo_adapter,
        "local://fail": fail_adapter,
    })

    workflow_dict = {
        "name": "test-fail",
        "nodes": {
            "producer": {
                "agent": "local://echo",
                "outputs": ["result"],
            },
            "consumer": {
                "agent": "local://fail",
                "outputs": ["final"],
                "depends_on": ["producer"],
            },
        },
    }

    summary = await orch.run_workflow(workflow_dict)
    assert summary.status == "failed"
    assert summary.failed_nodes >= 1


@pytest.mark.asyncio
async def test_artifacts_persisted() -> None:
    adapter = LocalPythonAdapter(handler=_echo_handler)
    orch = _build_orchestrator({"local://echo": adapter})

    workflow_dict = {
        "name": "test-artifacts",
        "nodes": {
            "a": {"agent": "local://echo", "outputs": ["result"]},
        },
    }

    summary = await orch.run_workflow(workflow_dict)
    artifacts = await orch.artifact_store.list_by_run(summary.run_id)
    assert len(artifacts) >= 1


@pytest.mark.asyncio
async def test_execution_records_persisted() -> None:
    adapter = LocalPythonAdapter(handler=_echo_handler)
    orch = _build_orchestrator({"local://echo": adapter})

    workflow_dict = {
        "name": "test-records",
        "nodes": {
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["out"], "depends_on": ["a"]},
        },
    }

    summary = await orch.run_workflow(workflow_dict)
    records = await orch.execution_store.list_records(summary.run_id)
    assert len(records) == 2
