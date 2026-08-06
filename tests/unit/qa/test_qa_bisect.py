"""Tests for binex.trace.bisect — run bisection / divergence detection.

TC-BSCT-001 through TC-BSCT-009.
"""

from __future__ import annotations

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.bisect import DivergencePoint, divergence_to_dict, find_divergence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    task_id: str,
    status: TaskStatus = TaskStatus.COMPLETED,
    run_id: str = "run_good",
    latency_ms: int = 100,
    input_artifact_refs: list[str] | None = None,
    output_artifact_refs: list[str] | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"rec_{run_id}_{task_id}",
        run_id=run_id,
        task_id=task_id,
        agent_id="llm://test",
        status=status,
        latency_ms=latency_ms,
        trace_id="trace_01",
        input_artifact_refs=input_artifact_refs or [],
        output_artifact_refs=output_artifact_refs or [],
    )


def _make_run(
    run_id: str,
    workflow_name: str = "test_wf",
    status: str = "completed",
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name=workflow_name,
        status=status,
        total_nodes=2,
    )


def _make_artifact(
    art_id: str,
    run_id: str,
    content: str,
    produced_by: str = "node_a",
) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type="llm_response",
        content=content,
        lineage=Lineage(produced_by=produced_by),
    )


# ---------------------------------------------------------------------------
# TC-BSCT-001: Identical runs -> None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identical_runs_return_none():
    """Two identical runs should produce no divergence."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good"))
    await exec_store.create_run(_make_run("run_bad"))

    await exec_store.record(_make_record("node_a", run_id="run_good"))
    await exec_store.record(_make_record("node_b", run_id="run_good"))
    await exec_store.record(_make_record("node_a", run_id="run_bad"))
    await exec_store.record(_make_record("node_b", run_id="run_bad"))

    result = await find_divergence(exec_store, art_store, "run_good", "run_bad")
    assert result is None


# ---------------------------------------------------------------------------
# TC-BSCT-002: Status divergence detected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_divergence_detected():
    """When one run has a completed node and the other has it failed, detect status divergence."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good"))
    await exec_store.create_run(_make_run("run_bad", status="failed"))

    # node_a: both completed
    await exec_store.record(_make_record("node_a", run_id="run_good"))
    await exec_store.record(_make_record("node_a", run_id="run_bad"))

    # node_b: good completed, bad failed
    await exec_store.record(_make_record("node_b", run_id="run_good"))
    await exec_store.record(
        _make_record("node_b", status=TaskStatus.FAILED, run_id="run_bad")
    )

    result = await find_divergence(exec_store, art_store, "run_good", "run_bad")

    assert result is not None
    assert result.node_id == "node_b"
    assert result.divergence_type == "status"
    assert result.good_status == "completed"
    assert result.bad_status == "failed"
    assert result.similarity is None


# ---------------------------------------------------------------------------
# TC-BSCT-003: Content divergence below threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_content_divergence_below_threshold():
    """Completed nodes with very different artifact content should trigger content divergence."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good"))
    await exec_store.create_run(_make_run("run_bad"))

    # node_a: both completed, with different content
    await exec_store.record(
        _make_record(
            "node_a",
            run_id="run_good",
            output_artifact_refs=["art_good_a"],
        )
    )
    await exec_store.record(
        _make_record(
            "node_a",
            run_id="run_bad",
            output_artifact_refs=["art_bad_a"],
        )
    )

    await art_store.store(
        _make_artifact("art_good_a", "run_good", "The quick brown fox jumps over the lazy dog")
    )
    await art_store.store(
        _make_artifact("art_bad_a", "run_bad", "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    )

    result = await find_divergence(exec_store, art_store, "run_good", "run_bad")

    assert result is not None
    assert result.node_id == "node_a"
    assert result.divergence_type == "content"
    assert result.similarity is not None
    assert result.similarity < 0.9
    assert result.good_status == "completed"
    assert result.bad_status == "completed"


# ---------------------------------------------------------------------------
# TC-BSCT-004: Raises ValueError for missing run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raises_for_missing_good_run():
    """Should raise ValueError when the good run does not exist."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_bad"))

    with pytest.raises(ValueError, match="Run 'run_good' not found"):
        await find_divergence(exec_store, art_store, "run_good", "run_bad")


@pytest.mark.asyncio
async def test_raises_for_missing_bad_run():
    """Should raise ValueError when the bad run does not exist."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good"))

    with pytest.raises(ValueError, match="Run 'run_bad' not found"):
        await find_divergence(exec_store, art_store, "run_good", "run_bad")


# ---------------------------------------------------------------------------
# TC-BSCT-005: Raises ValueError for mismatched workflows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_raises_for_mismatched_workflows():
    """Should raise ValueError when the two runs have different workflow names."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good", workflow_name="wf_alpha"))
    await exec_store.create_run(_make_run("run_bad", workflow_name="wf_beta"))

    with pytest.raises(ValueError, match="Workflows don't match"):
        await find_divergence(exec_store, art_store, "run_good", "run_bad")


# ---------------------------------------------------------------------------
# TC-BSCT-006: Custom threshold 0.5
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_threshold_half():
    """With a lower threshold of 0.5, moderately similar content should not diverge."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good"))
    await exec_store.create_run(_make_run("run_bad"))

    # Content that is moderately similar (~0.6-0.8 similarity)
    await exec_store.record(
        _make_record(
            "node_a",
            run_id="run_good",
            output_artifact_refs=["art_good_a"],
        )
    )
    await exec_store.record(
        _make_record(
            "node_a",
            run_id="run_bad",
            output_artifact_refs=["art_bad_a"],
        )
    )

    await art_store.store(
        _make_artifact("art_good_a", "run_good", "Hello world this is a test message")
    )
    await art_store.store(
        _make_artifact("art_bad_a", "run_bad", "Hello world this is a different message")
    )

    # Default threshold 0.9 would find divergence
    result_strict = await find_divergence(
        exec_store, art_store, "run_good", "run_bad", threshold=0.9
    )
    assert result_strict is not None
    assert result_strict.divergence_type == "content"

    # Threshold 0.5 should NOT find divergence (content is similar enough)
    result_relaxed = await find_divergence(
        exec_store, art_store, "run_good", "run_bad", threshold=0.5
    )
    assert result_relaxed is None


# ---------------------------------------------------------------------------
# TC-BSCT-007: Includes upstream_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upstream_context_included():
    """Upstream_context includes node_a when it feeds node_b."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    await exec_store.create_run(_make_run("run_good"))
    await exec_store.create_run(_make_run("run_bad", status="failed"))

    # node_a: both completed, outputs art_good_a / art_bad_a
    await exec_store.record(
        _make_record(
            "node_a",
            run_id="run_good",
            output_artifact_refs=["art_good_a"],
        )
    )
    await exec_store.record(
        _make_record(
            "node_a",
            run_id="run_bad",
            output_artifact_refs=["art_bad_a"],
        )
    )

    # node_b: good completed, bad failed; node_b takes node_a's output as input
    await exec_store.record(
        _make_record(
            "node_b",
            run_id="run_good",
            input_artifact_refs=["art_good_a"],
        )
    )
    await exec_store.record(
        _make_record(
            "node_b",
            status=TaskStatus.FAILED,
            run_id="run_bad",
            input_artifact_refs=["art_good_a"],
        )
    )

    result = await find_divergence(exec_store, art_store, "run_good", "run_bad")

    assert result is not None
    assert result.node_id == "node_b"
    assert result.divergence_type == "status"
    assert "node_a" in result.upstream_context


# ---------------------------------------------------------------------------
# TC-BSCT-008: divergence_to_dict with None divergence
# ---------------------------------------------------------------------------

def test_divergence_to_dict_none():
    """None divergence should produce a dict with message and null divergence."""
    result = divergence_to_dict("run_good", "run_bad", None)

    assert result["good_run_id"] == "run_good"
    assert result["bad_run_id"] == "run_bad"
    assert result["divergence"] is None
    assert result["message"] == "No divergence found"


# ---------------------------------------------------------------------------
# TC-BSCT-009: divergence_to_dict with DivergencePoint
# ---------------------------------------------------------------------------

def test_divergence_to_dict_with_point():
    """DivergencePoint should be fully serialized into the dict."""
    dp = DivergencePoint(
        node_id="node_b",
        divergence_type="status",
        similarity=None,
        good_status="completed",
        bad_status="failed",
        upstream_context=["node_a"],
    )

    result = divergence_to_dict("run_good", "run_bad", dp)

    assert result["good_run_id"] == "run_good"
    assert result["bad_run_id"] == "run_bad"
    assert "message" not in result

    div = result["divergence"]
    assert div["node_id"] == "node_b"
    assert div["divergence_type"] == "status"
    assert div["similarity"] is None
    assert div["good_status"] == "completed"
    assert div["bad_status"] == "failed"
    assert div["upstream_context"] == ["node_a"]


def test_divergence_to_dict_content_type():
    """Content divergence should include the similarity score."""
    dp = DivergencePoint(
        node_id="node_a",
        divergence_type="content",
        similarity=0.4523,
        good_status="completed",
        bad_status="completed",
        upstream_context=[],
    )

    result = divergence_to_dict("run_good", "run_bad", dp)

    div = result["divergence"]
    assert div["divergence_type"] == "content"
    assert div["similarity"] == 0.4523
    assert div["upstream_context"] == []
