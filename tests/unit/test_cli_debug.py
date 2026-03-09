"""Tests for binex debug CLI command."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.cli.debug import debug_cmd
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

RUN_ID = "run-debug-001"
TRACE_ID = "trace-001"
NOW = datetime(2026, 3, 8, 12, 0, 0, tzinfo=UTC)


def _make_populated_stores():
    """Create stores with a completed run for testing."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    import asyncio

    async def _populate():
        run = RunSummary(
            run_id=RUN_ID,
            workflow_name="test-wf",
            status="completed",
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=2),
            total_nodes=2,
            completed_nodes=2,
        )
        await exec_store.create_run(run)

        rec1 = ExecutionRecord(
            id="rec-1",
            run_id=RUN_ID,
            task_id="step_a",
            agent_id="llm://gpt-4",
            status=TaskStatus.COMPLETED,
            latency_ms=100,
            trace_id=TRACE_ID,
            prompt="Plan something",
            model="gpt-4",
            output_artifact_refs=["art-1"],
        )
        rec2 = ExecutionRecord(
            id="rec-2",
            run_id=RUN_ID,
            task_id="step_b",
            agent_id="llm://gpt-4",
            status=TaskStatus.COMPLETED,
            latency_ms=200,
            trace_id=TRACE_ID,
            prompt="Execute plan",
            model="gpt-4",
            input_artifact_refs=["art-1"],
            output_artifact_refs=["art-2"],
        )
        await exec_store.record(rec1)
        await exec_store.record(rec2)

        art1 = Artifact(
            id="art-1",
            run_id=RUN_ID,
            type="result",
            content="plan output",
            lineage=Lineage(produced_by="step_a"),
        )
        art2 = Artifact(
            id="art-2",
            run_id=RUN_ID,
            type="result",
            content="final output",
            lineage=Lineage(produced_by="step_b", derived_from=["art-1"]),
        )
        await art_store.store(art1)
        await art_store.store(art2)

    asyncio.run(_populate())
    return exec_store, art_store


# --- T012: test_debug_plain ---


def test_debug_plain():
    """CLI runner invokes `debug run_id`, exit code 0, output has node details."""
    stores = _make_populated_stores()

    with patch("binex.cli.debug._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(debug_cmd, [RUN_ID])

    assert result.exit_code == 0, result.output
    assert RUN_ID in result.output
    assert "step_a" in result.output
    assert "step_b" in result.output


# --- T013: test_debug_not_found ---


def test_debug_not_found():
    """CLI runner invokes `debug nonexistent`, exit code != 0."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    with patch("binex.cli.debug._get_stores", return_value=(exec_store, art_store)):
        runner = CliRunner()
        result = runner.invoke(debug_cmd, ["nonexistent"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "not found" in (result.output + (result.stderr_bytes or b"").decode()).lower()


# --- T022: test_debug_node_filter ---


def test_debug_node_filter():
    """CLI runner invokes `debug run_id --node step_a`, only step_a in output."""
    stores = _make_populated_stores()

    with patch("binex.cli.debug._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(debug_cmd, [RUN_ID, "--node", "step_a"])

    assert result.exit_code == 0, result.output
    assert "step_a" in result.output
    # step_b should not appear in node sections
    lines = result.output.split("\n")
    node_lines = [l for l in lines if l.startswith("-- ")]
    assert all("step_b" not in l for l in node_lines)


# --- T023: test_debug_errors_only ---


def _make_failed_stores():
    """Create stores with a failed run for testing."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    import asyncio

    async def _populate():
        run = RunSummary(
            run_id=RUN_ID,
            workflow_name="test-wf",
            status="failed",
            started_at=NOW,
            completed_at=NOW + timedelta(seconds=2),
            total_nodes=2,
            completed_nodes=1,
            failed_nodes=1,
        )
        await exec_store.create_run(run)

        rec1 = ExecutionRecord(
            id="rec-1",
            run_id=RUN_ID,
            task_id="step_a",
            agent_id="llm://gpt-4",
            status=TaskStatus.COMPLETED,
            latency_ms=100,
            trace_id=TRACE_ID,
            prompt="Plan something",
        )
        rec2 = ExecutionRecord(
            id="rec-2",
            run_id=RUN_ID,
            task_id="step_b",
            agent_id="llm://gpt-4",
            status=TaskStatus.FAILED,
            latency_ms=200,
            trace_id=TRACE_ID,
            prompt="Execute plan",
            error="Connection timeout",
        )
        await exec_store.record(rec1)
        await exec_store.record(rec2)

    asyncio.run(_populate())
    return exec_store, art_store


def test_debug_errors_only():
    """CLI runner invokes `debug run_id --errors`, only failed nodes in output."""
    stores = _make_failed_stores()

    with patch("binex.cli.debug._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(debug_cmd, [RUN_ID, "--errors"])

    assert result.exit_code == 0, result.output
    assert "step_b" in result.output
    assert "Connection timeout" in result.output
    lines = result.output.split("\n")
    node_lines = [l for l in lines if l.startswith("-- ")]
    assert all("step_a" not in l for l in node_lines)


# --- T035: test_debug_json ---


def test_debug_json():
    """CLI runner invokes `debug run_id --json`, output parses as valid JSON."""
    import json

    stores = _make_populated_stores()

    with patch("binex.cli.debug._get_stores", return_value=stores):
        runner = CliRunner()
        result = runner.invoke(debug_cmd, [RUN_ID, "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["run_id"] == RUN_ID
    assert "nodes" in data
    assert len(data["nodes"]) == 2
