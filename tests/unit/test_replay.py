"""Tests for replay engine — src/binex/runtime/replay.py."""

from __future__ import annotations

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.adapters.local import LocalPythonAdapter
from binex.runtime.dispatcher import Dispatcher
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def exec_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


def _make_dispatcher() -> Dispatcher:
    """Create a dispatcher with a default echo adapter for local:// agents."""
    async def _handler(task, inputs):
        content = {a.id: a.content for a in inputs} if inputs else {"msg": "no input"}
        return [
            Artifact(
                id=f"art_{task.node_id}_{task.run_id}",
                run_id=task.run_id,
                type="result",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )
        ]

    dispatcher = Dispatcher()
    dispatcher.register_adapter("local://echo", LocalPythonAdapter(handler=_handler))
    dispatcher.register_adapter("local://new_agent", LocalPythonAdapter(handler=_handler))
    return dispatcher


@pytest.fixture
def sample_workflow_dict() -> dict:
    return {
        "name": "test-pipeline",
        "description": "A -> B -> C pipeline",
        "nodes": {
            "a": {
                "agent": "local://echo",
                "system_prompt": "produce",
                "inputs": {},
                "outputs": ["result_a"],
            },
            "b": {
                "agent": "local://echo",
                "system_prompt": "transform",
                "inputs": {"data": "${a.result_a}"},
                "outputs": ["result_b"],
                "depends_on": ["a"],
            },
            "c": {
                "agent": "local://echo",
                "system_prompt": "consume",
                "inputs": {"data": "${b.result_b}"},
                "outputs": ["result_c"],
                "depends_on": ["b"],
            },
        },
    }


async def _seed_run(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    run_id: str = "run_original",
    workflow_name: str = "test-pipeline",
) -> RunSummary:
    """Seed stores with a completed 3-node run: a -> b -> c."""
    summary = RunSummary(
        run_id=run_id,
        workflow_name=workflow_name,
        status="completed",
        total_nodes=3,
        completed_nodes=3,
    )
    await exec_store.create_run(summary)

    # Artifacts
    art_a = Artifact(
        id=f"art_a_{run_id}", run_id=run_id, type="result_a",
        content={"val": "from_a"}, lineage=Lineage(produced_by="a"),
    )
    art_b = Artifact(
        id=f"art_b_{run_id}", run_id=run_id, type="result_b",
        content={"val": "from_b"},
        lineage=Lineage(produced_by="b", derived_from=[art_a.id]),
    )
    art_c = Artifact(
        id=f"art_c_{run_id}", run_id=run_id, type="result_c",
        content={"val": "from_c"},
        lineage=Lineage(produced_by="c", derived_from=[art_b.id]),
    )
    for art in [art_a, art_b, art_c]:
        await art_store.store(art)

    # Execution records
    for node_id, agent, in_refs, out_refs in [
        ("a", "local://echo", [], [art_a.id]),
        ("b", "local://echo", [art_a.id], [art_b.id]),
        ("c", "local://echo", [art_b.id], [art_c.id]),
    ]:
        rec = ExecutionRecord(
            id=f"rec_{node_id}_{run_id}",
            run_id=run_id,
            task_id=node_id,
            agent_id=agent,
            status=TaskStatus.COMPLETED,
            input_artifact_refs=in_refs,
            output_artifact_refs=out_refs,
            latency_ms=100,
            trace_id="trace_001",
        )
        await exec_store.record(rec)

    return summary


@pytest.mark.asyncio
async def test_replay_from_step_creates_new_run(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """Replay from step 'b' should create a new run with forked_from/forked_at_step set."""
    from binex.runtime.replay import ReplayEngine

    await _seed_run(exec_store, art_store)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    result = await engine.replay(
        original_run_id="run_original",
        workflow=sample_workflow_dict,
        from_step="b",
    )

    assert result.run_id != "run_original"
    assert result.forked_from == "run_original"
    assert result.forked_at_step == "b"
    assert result.status in ("completed", "running")


@pytest.mark.asyncio
async def test_replay_caches_upstream_artifacts(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """Steps before --from should be marked as cached, reusing original artifacts."""
    from binex.runtime.replay import ReplayEngine

    await _seed_run(exec_store, art_store)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    result = await engine.replay(
        original_run_id="run_original",
        workflow=sample_workflow_dict,
        from_step="b",
    )

    # Step 'a' should have a cached execution record
    records = await exec_store.list_records(result.run_id)
    cached_records = [r for r in records if r.task_id == "a"]
    assert len(cached_records) == 1
    assert cached_records[0].status == TaskStatus.COMPLETED
    # Cached record should reference original artifacts
    assert cached_records[0].output_artifact_refs == [f"art_a_run_original"]


@pytest.mark.asyncio
async def test_replay_re_executes_from_step(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """Steps from --from onward should be re-executed (new records created)."""
    from binex.runtime.replay import ReplayEngine

    await _seed_run(exec_store, art_store)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    result = await engine.replay(
        original_run_id="run_original",
        workflow=sample_workflow_dict,
        from_step="b",
    )

    records = await exec_store.list_records(result.run_id)
    re_executed = [r for r in records if r.task_id in ("b", "c")]
    assert len(re_executed) == 2
    for rec in re_executed:
        assert rec.run_id == result.run_id


@pytest.mark.asyncio
async def test_replay_with_agent_swap(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """--agent node=agent should swap the agent for that node during replay."""
    from binex.runtime.replay import ReplayEngine

    await _seed_run(exec_store, art_store)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    result = await engine.replay(
        original_run_id="run_original",
        workflow=sample_workflow_dict,
        from_step="b",
        agent_swaps={"b": "local://new_agent"},
    )

    records = await exec_store.list_records(result.run_id)
    b_record = next(r for r in records if r.task_id == "b")
    assert b_record.agent_id == "local://new_agent"


@pytest.mark.asyncio
async def test_replay_invalid_step_raises(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """Replaying from a non-existent step should raise ValueError."""
    from binex.runtime.replay import ReplayEngine

    await _seed_run(exec_store, art_store)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    with pytest.raises(ValueError, match="not found"):
        await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="nonexistent",
        )


@pytest.mark.asyncio
async def test_replay_invalid_run_raises(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """Replaying from a non-existent run should raise ValueError."""
    from binex.runtime.replay import ReplayEngine

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    with pytest.raises(ValueError, match="not found"):
        await engine.replay(
            original_run_id="run_nonexistent",
            workflow=sample_workflow_dict,
            from_step="b",
        )


@pytest.mark.asyncio
async def test_replay_from_first_step_re_executes_all(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    sample_workflow_dict: dict,
):
    """Replaying from the first step should re-execute everything."""
    from binex.runtime.replay import ReplayEngine

    await _seed_run(exec_store, art_store)

    engine = ReplayEngine(
        execution_store=exec_store,
        artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )

    result = await engine.replay(
        original_run_id="run_original",
        workflow=sample_workflow_dict,
        from_step="a",
    )

    records = await exec_store.list_records(result.run_id)
    # All 3 nodes should be re-executed (none cached)
    assert len(records) == 3
    # No cached records should reference original run's artifacts
    for rec in records:
        assert rec.run_id == result.run_id
