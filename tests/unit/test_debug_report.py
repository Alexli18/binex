"""Tests for debug report builder and formatters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.debug_report import (
    DebugReport,
    NodeReport,
    build_debug_report,
    format_debug_report,
)

RUN_ID = "run-001"
TRACE_ID = "trace-001"
NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC)


async def _make_stores(
    *,
    run: RunSummary | None = None,
    records: list[ExecutionRecord] | None = None,
    artifacts: list[Artifact] | None = None,
) -> tuple[InMemoryExecutionStore, InMemoryArtifactStore]:
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    if run:
        await exec_store.create_run(run)
    for rec in records or []:
        await exec_store.record(rec)
    for art in artifacts or []:
        await art_store.store(art)
    return exec_store, art_store


def _run_summary(
    *,
    status: str = "completed",
    total: int = 2,
    completed: int = 2,
    failed: int = 0,
    started: datetime = NOW,
    finished: datetime | None = None,
) -> RunSummary:
    return RunSummary(
        run_id=RUN_ID,
        workflow_name="test-workflow",
        status=status,
        started_at=started,
        completed_at=finished or started + timedelta(seconds=5),
        total_nodes=total,
        completed_nodes=completed,
        failed_nodes=failed,
    )


def _record(
    task_id: str,
    *,
    status: TaskStatus = TaskStatus.COMPLETED,
    latency: int = 100,
    prompt: str | None = "Do something",
    model: str | None = "gpt-4",
    error: str | None = None,
    input_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"rec-{task_id}",
        run_id=RUN_ID,
        task_id=task_id,
        agent_id=f"llm://{model or 'default'}",
        status=status,
        input_artifact_refs=input_refs or [],
        output_artifact_refs=output_refs or [],
        prompt=prompt,
        model=model,
        latency_ms=latency,
        trace_id=TRACE_ID,
        error=error,
    )


def _artifact(
    art_id: str,
    *,
    produced_by: str = "step_a",
    content: str = "hello world",
    art_type: str = "result",
) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=RUN_ID,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=produced_by),
    )


# --- T002: test_build_debug_report_basic ---


@pytest.mark.asyncio
async def test_build_debug_report_basic():
    """Report from populated stores returns correct run_id, workflow_name, status, node count."""
    run = _run_summary(total=2, completed=2)
    records = [_record("step_a"), _record("step_b")]
    exec_store, art_store = await _make_stores(run=run, records=records)

    report = await build_debug_report(exec_store, art_store, RUN_ID)

    assert report is not None
    assert isinstance(report, DebugReport)
    assert report.run_id == RUN_ID
    assert report.workflow_name == "test-workflow"
    assert report.status == "completed"
    assert len(report.nodes) == 2


# --- T003: test_report_contains_completed_node ---


@pytest.mark.asyncio
async def test_report_contains_completed_node():
    """Completed node has correct status, latency, prompt, output artifacts."""
    out_art = _artifact("art-out", produced_by="step_a")
    run = _run_summary(total=1, completed=1)
    records = [_record("step_a", latency=250, output_refs=["art-out"])]
    exec_store, art_store = await _make_stores(
        run=run, records=records, artifacts=[out_art]
    )

    report = await build_debug_report(exec_store, art_store, RUN_ID)

    assert report is not None
    node = report.nodes[0]
    assert node.node_id == "step_a"
    assert node.status == "completed"
    assert node.latency_ms == 250
    assert node.prompt == "Do something"
    assert len(node.output_artifacts) == 1
    assert node.output_artifacts[0].id == "art-out"


# --- T004: test_report_contains_failed_node ---


@pytest.mark.asyncio
async def test_report_contains_failed_node():
    """Failed node has error message and input artifacts."""
    in_art = _artifact("art-in", produced_by="step_x")
    run = _run_summary(status="failed", total=1, completed=0, failed=1)
    records = [
        _record(
            "step_a",
            status=TaskStatus.FAILED,
            error="Connection refused",
            input_refs=["art-in"],
        )
    ]
    exec_store, art_store = await _make_stores(
        run=run, records=records, artifacts=[in_art]
    )

    report = await build_debug_report(exec_store, art_store, RUN_ID)

    assert report is not None
    node = report.nodes[0]
    assert node.status == "failed"
    assert node.error == "Connection refused"
    assert len(node.input_artifacts) == 1
    assert node.input_artifacts[0].id == "art-in"


# --- T005: test_report_contains_skipped_node ---


@pytest.mark.asyncio
async def test_report_contains_skipped_node():
    """Skipped nodes inferred from total_nodes minus recorded; blocked_by contains failed node IDs."""
    run = _run_summary(status="failed", total=3, completed=1, failed=1)
    records = [
        _record("step_a"),
        _record("step_b", status=TaskStatus.FAILED, error="boom"),
    ]
    exec_store, art_store = await _make_stores(run=run, records=records)

    report = await build_debug_report(exec_store, art_store, RUN_ID)

    assert report is not None
    assert len(report.nodes) == 3
    skipped = [n for n in report.nodes if n.status == "skipped"]
    assert len(skipped) == 1
    assert skipped[0].node_id.startswith("<skipped-")
    assert "step_b" in skipped[0].blocked_by


# --- T006: test_report_not_found ---


@pytest.mark.asyncio
async def test_report_not_found():
    """Returns None for nonexistent run_id."""
    exec_store, art_store = await _make_stores()

    report = await build_debug_report(exec_store, art_store, "nonexistent")

    assert report is None


# --- T007: test_report_duration ---


@pytest.mark.asyncio
async def test_report_duration():
    """duration_ms computed from started_at/completed_at."""
    started = NOW
    finished = started + timedelta(seconds=3, milliseconds=500)
    run = _run_summary(started=started, finished=finished, total=1, completed=1)
    records = [_record("step_a")]
    exec_store, art_store = await _make_stores(run=run, records=records)

    report = await build_debug_report(exec_store, art_store, RUN_ID)

    assert report is not None
    assert report.duration_ms == 3500


# --- T011: test_format_plain_text ---


@pytest.mark.asyncio
async def test_format_plain_text():
    """Output contains run_id, workflow name, status, all node IDs, error messages."""
    run = _run_summary(status="failed", total=2, completed=1, failed=1)
    records = [
        _record("step_a", output_refs=["art-out"]),
        _record("step_b", status=TaskStatus.FAILED, error="timeout hit"),
    ]
    out_art = _artifact("art-out", produced_by="step_a")
    exec_store, art_store = await _make_stores(
        run=run, records=records, artifacts=[out_art]
    )
    report = await build_debug_report(exec_store, art_store, RUN_ID)
    assert report is not None

    output = format_debug_report(report)

    assert RUN_ID in output
    assert "test-workflow" in output
    assert "failed" in output
    assert "step_a" in output
    assert "step_b" in output
    assert "timeout hit" in output


# --- T020: test_format_plain_text_node_filter ---


@pytest.mark.asyncio
async def test_format_plain_text_node_filter():
    """Output contains filtered node only, other nodes absent."""
    run = _run_summary(total=2, completed=2)
    records = [_record("step_a"), _record("step_b")]
    exec_store, art_store = await _make_stores(run=run, records=records)
    report = await build_debug_report(exec_store, art_store, RUN_ID)
    assert report is not None

    output = format_debug_report(report, node_filter="step_a")

    assert "step_a" in output
    assert "step_b" not in output


# --- T021: test_format_plain_text_errors_only ---


@pytest.mark.asyncio
async def test_format_plain_text_errors_only():
    """Output contains failed node, completed node absent."""
    run = _run_summary(status="failed", total=2, completed=1, failed=1)
    records = [
        _record("step_a"),
        _record("step_b", status=TaskStatus.FAILED, error="crash"),
    ]
    exec_store, art_store = await _make_stores(run=run, records=records)
    report = await build_debug_report(exec_store, art_store, RUN_ID)
    assert report is not None

    output = format_debug_report(report, errors_only=True)

    assert "step_b" in output
    assert "crash" in output
    # step_a is completed so should be filtered out from node sections
    # but header still mentions the workflow
    lines = output.split("\n")
    node_lines = [l for l in lines if l.startswith("-- ")]
    assert all("step_a" not in l for l in node_lines)


# --- T034: test_format_json ---


@pytest.mark.asyncio
async def test_format_json():
    """JSON dict has correct run_id, status, nodes list."""
    run = _run_summary(total=2, completed=2)
    records = [
        _record("step_a", output_refs=["art-out"]),
        _record("step_b"),
    ]
    out_art = _artifact("art-out", produced_by="step_a")
    exec_store, art_store = await _make_stores(
        run=run, records=records, artifacts=[out_art]
    )
    report = await build_debug_report(exec_store, art_store, RUN_ID)
    assert report is not None

    from binex.trace.debug_report import format_debug_report_json

    data = format_debug_report_json(report)

    assert data["run_id"] == RUN_ID
    assert data["status"] == "completed"
    assert data["workflow_name"] == "test-workflow"
    assert len(data["nodes"]) == 2
    assert data["nodes"][0]["node_id"] == "step_a"
    assert len(data["nodes"][0]["output_artifacts"]) == 1
