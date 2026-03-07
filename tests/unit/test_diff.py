"""Tests for diff engine — src/binex/trace/diff.py."""

from __future__ import annotations

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def exec_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


async def _seed_two_runs(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
) -> tuple[str, str]:
    """Create two runs with slightly different results for diff testing."""
    for run_id, status_b, content_b, latency_b in [
        ("run_a", TaskStatus.COMPLETED, {"val": "result_b_v1"}, 100),
        ("run_b", TaskStatus.COMPLETED, {"val": "result_b_v2"}, 200),
    ]:
        summary = RunSummary(
            run_id=run_id,
            workflow_name="test-pipeline",
            status="completed",
            total_nodes=2,
            completed_nodes=2,
        )
        await exec_store.create_run(summary)

        art_a = Artifact(
            id=f"art_a_{run_id}", run_id=run_id, type="result_a",
            content={"val": "same_value"}, lineage=Lineage(produced_by="a"),
        )
        art_b = Artifact(
            id=f"art_b_{run_id}", run_id=run_id, type="result_b",
            content=content_b,
            lineage=Lineage(produced_by="b", derived_from=[art_a.id]),
        )
        for art in [art_a, art_b]:
            await art_store.store(art)

        for node_id, agent, in_refs, out_refs, latency in [
            ("a", "local://echo", [], [art_a.id], 100),
            ("b", "local://echo", [art_a.id], [art_b.id], latency_b),
        ]:
            rec = ExecutionRecord(
                id=f"rec_{node_id}_{run_id}",
                run_id=run_id,
                task_id=node_id,
                agent_id=agent,
                status=status_b,
                input_artifact_refs=in_refs,
                output_artifact_refs=out_refs,
                latency_ms=latency,
                trace_id=f"trace_{run_id}",
            )
            await exec_store.record(rec)

    return "run_a", "run_b"


@pytest.mark.asyncio
async def test_diff_returns_step_comparisons(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """Diff should return per-step comparison between two runs."""
    from binex.trace.diff import diff_runs

    run_a, run_b = await _seed_two_runs(exec_store, art_store)

    result = await diff_runs(exec_store, art_store, run_a, run_b)

    assert "steps" in result
    assert len(result["steps"]) == 2  # a and b


@pytest.mark.asyncio
async def test_diff_detects_artifact_differences(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """Diff should flag steps where artifact content differs."""
    from binex.trace.diff import diff_runs

    run_a, run_b = await _seed_two_runs(exec_store, art_store)

    result = await diff_runs(exec_store, art_store, run_a, run_b)

    step_b = next(s for s in result["steps"] if s["task_id"] == "b")
    assert step_b["artifacts_changed"] is True

    step_a = next(s for s in result["steps"] if s["task_id"] == "a")
    assert step_a["artifacts_changed"] is False


@pytest.mark.asyncio
async def test_diff_detects_latency_differences(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """Diff should include latency comparison."""
    from binex.trace.diff import diff_runs

    run_a, run_b = await _seed_two_runs(exec_store, art_store)

    result = await diff_runs(exec_store, art_store, run_a, run_b)

    step_b = next(s for s in result["steps"] if s["task_id"] == "b")
    assert step_b["latency_a"] == 100
    assert step_b["latency_b"] == 200


@pytest.mark.asyncio
async def test_diff_json_output(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """Diff result should be JSON-serializable."""
    import json

    from binex.trace.diff import diff_runs

    run_a, run_b = await _seed_two_runs(exec_store, art_store)

    result = await diff_runs(exec_store, art_store, run_a, run_b)

    # Should not raise
    json_str = json.dumps(result, default=str)
    assert len(json_str) > 0


@pytest.mark.asyncio
async def test_diff_format_text(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """format_diff should produce a human-readable text comparison."""
    from binex.trace.diff import diff_runs, format_diff

    run_a, run_b = await _seed_two_runs(exec_store, art_store)

    result = await diff_runs(exec_store, art_store, run_a, run_b)
    text = format_diff(result)

    assert "run_a" in text
    assert "run_b" in text
    assert "b" in text  # step name


@pytest.mark.asyncio
async def test_diff_missing_run_raises(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """Diff with non-existent run should raise ValueError."""
    from binex.trace.diff import diff_runs

    with pytest.raises(ValueError, match="not found"):
        await diff_runs(exec_store, art_store, "nonexistent_a", "nonexistent_b")


@pytest.mark.asyncio
async def test_diff_detects_status_changes(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
):
    """Diff should detect when step status differs between runs."""
    from binex.trace.diff import diff_runs

    # Create run_a with completed step b, run_b with failed step b
    summary_a = RunSummary(
        run_id="run_a", workflow_name="test", status="completed",
        total_nodes=1, completed_nodes=1,
    )
    summary_b = RunSummary(
        run_id="run_b", workflow_name="test", status="failed",
        total_nodes=1, failed_nodes=1,
    )
    await exec_store.create_run(summary_a)
    await exec_store.create_run(summary_b)

    rec_a = ExecutionRecord(
        id="rec_x_a", run_id="run_a", task_id="x", agent_id="local://echo",
        status=TaskStatus.COMPLETED, latency_ms=50, trace_id="t1",
        output_artifact_refs=["art_x_a"],
    )
    rec_b = ExecutionRecord(
        id="rec_x_b", run_id="run_b", task_id="x", agent_id="local://echo",
        status=TaskStatus.FAILED, latency_ms=50, trace_id="t2",
        error="timeout", output_artifact_refs=[],
    )
    await exec_store.record(rec_a)
    await exec_store.record(rec_b)

    result = await diff_runs(exec_store, art_store, "run_a", "run_b")

    step_x = next(s for s in result["steps"] if s["task_id"] == "x")
    assert step_x["status_a"] == "completed"
    assert step_x["status_b"] == "failed"
    assert step_x["status_changed"] is True
