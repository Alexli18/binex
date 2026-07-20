"""Tests for the resume engine — src/binex/runtime/resume.py."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.runtime.dispatcher import Dispatcher
from binex.runtime.resume import ResumeEngine, ResumeError
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def exec_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


def _make_dispatcher() -> Dispatcher:
    async def _handler(task, inputs):
        content = {a.id: a.content for a in inputs} if inputs else {"msg": "seed"}
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
    return dispatcher


def _diamond_workflow() -> dict:
    """Diamond DAG: a -> {b, c} -> d."""
    return {
        "name": "diamond",
        "description": "a fans out to b,c which fan in to d",
        "nodes": {
            "a": {"agent": "local://echo", "system_prompt": "start",
                  "inputs": {}, "outputs": ["ra"]},
            "b": {"agent": "local://echo", "system_prompt": "left",
                  "inputs": {"x": "${a.ra}"}, "outputs": ["rb"],
                  "depends_on": ["a"]},
            "c": {"agent": "local://echo", "system_prompt": "right",
                  "inputs": {"x": "${a.ra}"}, "outputs": ["rc"],
                  "depends_on": ["a"]},
            "d": {"agent": "local://echo", "system_prompt": "join",
                  "inputs": {"x": "${b.rb}", "y": "${c.rc}"}, "outputs": ["rd"],
                  "depends_on": ["b", "c"]},
        },
    }


def _write_workflow(tmp_path: Path, wf: dict) -> str:
    path = tmp_path / "diamond.yaml"
    path.write_text(yaml.dump(wf, sort_keys=True))
    return str(path)


async def _seed_partial_run(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    workflow_path: str,
    *,
    status: str = "failed",
    total_cost: float = 0.0,
    run_id: str = "run_parent",
    workflow_hash: str | None = None,
) -> RunSummary:
    """Seed a diamond run where a,b completed, c failed, d never ran."""
    summary = RunSummary(
        run_id=run_id,
        workflow_name="diamond",
        workflow_path=workflow_path,
        workflow_hash=workflow_hash,
        status=status,
        total_nodes=4,
        completed_nodes=2,
        failed_nodes=1,
        total_cost=total_cost,
    )
    await exec_store.create_run(summary)

    art_a = Artifact(id=f"art_a_{run_id}", run_id=run_id, type="ra",
                     content={"v": "a"}, lineage=Lineage(produced_by="a"))
    art_b = Artifact(id=f"art_b_{run_id}", run_id=run_id, type="rb",
                     content={"v": "b"},
                     lineage=Lineage(produced_by="b", derived_from=[art_a.id]))
    for art in (art_a, art_b):
        await art_store.store(art)

    for node_id, refs_in, refs_out, st in [
        ("a", [], [art_a.id], TaskStatus.COMPLETED),
        ("b", [art_a.id], [art_b.id], TaskStatus.COMPLETED),
        ("c", [art_a.id], [], TaskStatus.FAILED),
    ]:
        await exec_store.record(ExecutionRecord(
            id=f"rec_{node_id}_{run_id}", run_id=run_id, task_id=node_id,
            agent_id="local://echo", status=st,
            input_artifact_refs=refs_in, output_artifact_refs=refs_out,
            latency_ms=10, trace_id="trace_parent",
            error="boom" if st == TaskStatus.FAILED else None,
        ))

    return summary


def _engine(exec_store, art_store) -> ResumeEngine:
    return ResumeEngine(
        execution_store=exec_store, artifact_store=art_store,
        dispatcher=_make_dispatcher(),
    )


@pytest.mark.asyncio
async def test_resume_partitions_by_status(exec_store, art_store, tmp_path):
    """Completed a,b are cached; failed c and pending d are re-run."""
    wf_path = _write_workflow(tmp_path, _diamond_workflow())
    await _seed_partial_run(exec_store, art_store, wf_path)

    result = await _engine(exec_store, art_store).resume("run_parent")

    assert result.summary.resumed_from == "run_parent"
    assert result.summary.run_id != "run_parent"
    assert result.cached_nodes == 2
    assert result.resumed_nodes == 2
    assert result.summary.status == "completed"

    records = await exec_store.list_records(result.summary.run_id)
    by_node = {r.task_id: r for r in records}
    # a, b cached (copied); c, d freshly executed — all under the child run
    assert set(by_node) == {"a", "b", "c", "d"}
    assert by_node["a"].output_artifact_refs == ["art_a_run_parent"]
    assert by_node["c"].status == TaskStatus.COMPLETED  # re-run succeeded


@pytest.mark.asyncio
async def test_resume_completed_run_rejected(exec_store, art_store, tmp_path):
    wf_path = _write_workflow(tmp_path, _diamond_workflow())
    await _seed_partial_run(exec_store, art_store, wf_path, status="completed")

    with pytest.raises(ResumeError, match="already completed"):
        await _engine(exec_store, art_store).resume("run_parent")


@pytest.mark.asyncio
async def test_resume_running_refused_without_force(exec_store, art_store, tmp_path):
    wf_path = _write_workflow(tmp_path, _diamond_workflow())
    await _seed_partial_run(exec_store, art_store, wf_path, status="running")

    with pytest.raises(ResumeError, match="still marked 'running'"):
        await _engine(exec_store, art_store).resume("run_parent")

    # --force overrides
    result = await _engine(exec_store, art_store).resume("run_parent", force=True)
    assert result.summary.status == "completed"


@pytest.mark.asyncio
async def test_resume_cancelled_warns_but_proceeds(exec_store, art_store, tmp_path):
    wf_path = _write_workflow(tmp_path, _diamond_workflow())
    await _seed_partial_run(exec_store, art_store, wf_path, status="cancelled")

    result = await _engine(exec_store, art_store).resume("run_parent")
    assert any("cancelled" in w for w in result.warnings)
    assert result.summary.status == "completed"


@pytest.mark.asyncio
async def test_resume_from_node_cascade(exec_store, art_store, tmp_path):
    """--from b invalidates b and its descendant d, even though b completed."""
    wf_path = _write_workflow(tmp_path, _diamond_workflow())
    await _seed_partial_run(exec_store, art_store, wf_path)

    result = await _engine(exec_store, art_store).resume("run_parent", from_node="b")

    # Cached should now only be {a}; b, c, d all re-run.
    assert result.cached_nodes == 1
    assert result.resumed_nodes == 3


@pytest.mark.asyncio
async def test_resume_cumulative_budget(exec_store, art_store, tmp_path):
    """Child run starts from the parent's accumulated cost."""
    wf_path = _write_workflow(tmp_path, _diamond_workflow())
    await _seed_partial_run(exec_store, art_store, wf_path, total_cost=5.0)

    result = await _engine(exec_store, art_store).resume("run_parent")
    # Echo adapter adds no cost, so cumulative == parent's prior cost.
    assert result.summary.total_cost == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_resume_run_not_found(exec_store, art_store):
    with pytest.raises(ResumeError, match="not found"):
        await _engine(exec_store, art_store).resume("run_missing")


@pytest.mark.asyncio
async def test_resume_per_node_drift_reruns_changed_node(
    exec_store, art_store, tmp_path,
):
    """A completed node whose definition changed is re-run, not cached."""
    original = _diamond_workflow()
    wf_path = _write_workflow(tmp_path, original)

    # Store the ORIGINAL snapshot and hash it, as the orchestrator would.
    snap = yaml.dump(original, sort_keys=True)
    wf_hash = await exec_store.store_workflow_snapshot(snap, version=1)
    await _seed_partial_run(
        exec_store, art_store, wf_path, workflow_hash=wf_hash,
    )

    # Now change node b's prompt on disk (drift).
    drifted = _diamond_workflow()
    drifted["nodes"]["b"]["system_prompt"] = "CHANGED"
    _write_workflow(tmp_path, drifted)

    result = await _engine(exec_store, art_store).resume("run_parent")

    # b changed -> only a is cacheable; b, c, d re-run.
    assert result.cached_nodes == 1
    assert result.resumed_nodes == 3
