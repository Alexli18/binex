"""Replay must not silently reuse cached upstream that no longer matches the workflow.

The original run stores a workflow snapshot (``RunSummary.workflow_hash``).
Replay reuses every node before ``from_step`` verbatim — so if one of those
node definitions changed in the workflow file since the original run, the
cached artifact is stale relative to the file and the replay result is
misleading. These tests pin the gate that catches it.
"""

from __future__ import annotations

import pytest
import yaml

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.models.workflow import WorkflowSpec
from binex.runtime.dispatcher import Dispatcher
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def exec_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


def _make_dispatcher() -> Dispatcher:
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
    dispatcher.register_adapter(
        "local://something_else", LocalPythonAdapter(handler=_handler),
    )
    return dispatcher


def _workflow_dict() -> dict:
    return {
        "name": "test-pipeline",
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
    *,
    with_snapshot: bool = True,
    run_id: str = "run_original",
) -> RunSummary:
    """Seed a completed 3-node run, optionally with its workflow snapshot."""
    workflow_hash = None
    if with_snapshot:
        spec = WorkflowSpec(**_workflow_dict())
        content = yaml.dump(spec.model_dump(exclude={"source_path"}), sort_keys=True)
        workflow_hash = await exec_store.store_workflow_snapshot(
            content, version=spec.version,
        )

    summary = RunSummary(
        run_id=run_id,
        workflow_name="test-pipeline",
        status="completed",
        total_nodes=3,
        completed_nodes=3,
        workflow_hash=workflow_hash,
    )
    await exec_store.create_run(summary)

    prev: list[str] = []
    for node_id in ("a", "b", "c"):
        art = Artifact(
            id=f"art_{node_id}_{run_id}", run_id=run_id, type=f"result_{node_id}",
            content={"val": f"from_{node_id}"},
            lineage=Lineage(produced_by=node_id, derived_from=prev),
        )
        await art_store.store(art)
        await exec_store.record(ExecutionRecord(
            id=f"rec_{node_id}_{run_id}",
            run_id=run_id,
            task_id=node_id,
            agent_id="local://echo",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=prev,
            output_artifact_refs=[art.id],
            latency_ms=100,
            trace_id="trace_001",
        ))
        prev = [art.id]

    return summary


def _engine(exec_store, art_store):
    from binex.runtime.replay import ReplayEngine

    return ReplayEngine(
        execution_store=exec_store, artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )


@pytest.mark.asyncio
async def test_replay_rejects_drifted_cached_node(exec_store, art_store):
    """Editing an upstream node's prompt must block replay from a later step."""
    from binex.runtime.replay import WorkflowDriftError

    await _seed_run(exec_store, art_store)

    edited = _workflow_dict()
    edited["nodes"]["a"]["system_prompt"] = "produce, but differently now"

    with pytest.raises(WorkflowDriftError) as excinfo:
        await _engine(exec_store, art_store).replay(
            original_run_id="run_original", workflow=edited, from_step="b",
        )

    assert excinfo.value.drifted == ["a"]


@pytest.mark.asyncio
async def test_drift_error_names_node_and_offers_escape_hatch(exec_store, art_store):
    """The error must say which node drifted and how to proceed anyway."""
    from binex.runtime.replay import WorkflowDriftError

    await _seed_run(exec_store, art_store)

    edited = _workflow_dict()
    edited["nodes"]["a"]["agent"] = "local://something_else"

    with pytest.raises(WorkflowDriftError) as excinfo:
        await _engine(exec_store, art_store).replay(
            original_run_id="run_original", workflow=edited, from_step="c",
        )

    message = str(excinfo.value)
    assert "'a'" in message
    assert "--allow-drift" in message


@pytest.mark.asyncio
async def test_replay_proceeds_when_drift_explicitly_allowed(exec_store, art_store):
    """--allow-drift is the escape hatch: reuse the stale cache knowingly."""
    await _seed_run(exec_store, art_store)

    edited = _workflow_dict()
    edited["nodes"]["a"]["system_prompt"] = "changed"

    result = await _engine(exec_store, art_store).replay(
        original_run_id="run_original", workflow=edited, from_step="b",
        allow_drift=True,
    )

    assert result.status == "completed"
    assert result.forked_from == "run_original"


@pytest.mark.asyncio
async def test_changes_at_or_after_from_step_are_not_drift(exec_store, art_store):
    """Editing the node you replay (or its downstream) is the entire point."""
    await _seed_run(exec_store, art_store)

    edited = _workflow_dict()
    edited["nodes"]["b"]["system_prompt"] = "transform, v2"
    edited["nodes"]["c"]["system_prompt"] = "consume, v2"

    result = await _engine(exec_store, art_store).replay(
        original_run_id="run_original", workflow=edited, from_step="b",
    )

    assert result.status == "completed"


@pytest.mark.asyncio
async def test_unchanged_workflow_replays_without_drift(exec_store, art_store):
    """The happy path must not regress: identical workflow, no error."""
    await _seed_run(exec_store, art_store)

    result = await _engine(exec_store, art_store).replay(
        original_run_id="run_original", workflow=_workflow_dict(), from_step="b",
    )

    assert result.status == "completed"


@pytest.mark.asyncio
async def test_run_without_snapshot_cannot_drift_check(exec_store, art_store):
    """Legacy runs have no snapshot — replay proceeds rather than hard-failing."""
    await _seed_run(exec_store, art_store, with_snapshot=False)

    edited = _workflow_dict()
    edited["nodes"]["a"]["system_prompt"] = "changed"

    result = await _engine(exec_store, art_store).replay(
        original_run_id="run_original", workflow=edited, from_step="b",
    )

    assert result.status == "completed"


@pytest.mark.asyncio
async def test_resolved_user_var_is_not_drift(exec_store, art_store):
    """``${user.x}`` is a load-time binding, not part of a node's definition.

    The original run snapshots the spec *after* substitution (``data: hello``),
    while replay reloads the workflow file *before* it (``data: ${user.input}``).
    Comparing those naively flags every parameterised workflow as drifted.
    """
    from binex.runtime.replay import ReplayEngine

    resolved = _workflow_dict()
    resolved["nodes"]["a"]["inputs"] = {"data": "hello"}

    spec = WorkflowSpec(**resolved)
    content = yaml.dump(spec.model_dump(exclude={"source_path"}), sort_keys=True)
    workflow_hash = await exec_store.store_workflow_snapshot(
        content, version=spec.version,
    )
    await _seed_run(exec_store, art_store, with_snapshot=False)
    run = await exec_store.get_run("run_original")
    run.workflow_hash = workflow_hash
    await exec_store.update_run(run)

    unresolved = _workflow_dict()
    unresolved["nodes"]["a"]["inputs"] = {"data": "${user.input}"}

    engine = ReplayEngine(
        execution_store=exec_store, artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )
    result = await engine.replay(
        original_run_id="run_original", workflow=unresolved, from_step="b",
    )

    assert result.status == "completed"


@pytest.mark.asyncio
async def test_changed_literal_input_is_still_drift(exec_store, art_store):
    """Relaxing user-var comparison must not blind the check to real edits."""
    from binex.runtime.replay import ReplayEngine, WorkflowDriftError

    await _seed_run(exec_store, art_store)

    edited = _workflow_dict()
    edited["nodes"]["a"]["inputs"] = {"data": "a literal that was not there"}

    engine = ReplayEngine(
        execution_store=exec_store, artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )
    with pytest.raises(WorkflowDriftError):
        await engine.replay(
            original_run_id="run_original", workflow=edited, from_step="b",
        )


@pytest.mark.asyncio
async def test_replay_stores_its_own_workflow_snapshot(exec_store, art_store):
    """A replay run must itself be drift-checkable when replayed later."""
    await _seed_run(exec_store, art_store)

    result = await _engine(exec_store, art_store).replay(
        original_run_id="run_original", workflow=_workflow_dict(), from_step="b",
    )

    assert result.workflow_hash
    snapshot = await exec_store.get_workflow_snapshot(result.workflow_hash)
    assert snapshot is not None
    assert "test-pipeline" in snapshot["content"]
