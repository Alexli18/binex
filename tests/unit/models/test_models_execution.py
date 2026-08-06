"""Tests for ExecutionRecord and RunSummary models."""

from datetime import UTC, datetime

from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus


class TestExecutionRecord:
    def test_create_minimal(self) -> None:
        er = ExecutionRecord(
            id="rec_01",
            run_id="run_01",
            task_id="planner",
            agent_id="local://planner",
            status=TaskStatus.COMPLETED,
            latency_ms=1500,
            trace_id="trace_01",
        )
        assert er.id == "rec_01"
        assert er.parent_task_id is None
        assert er.input_artifact_refs == []
        assert er.output_artifact_refs == []
        assert er.prompt is None
        assert er.model is None
        assert er.tool_calls is None
        assert er.error is None
        assert isinstance(er.timestamp, datetime)

    def test_create_full(self) -> None:
        er = ExecutionRecord(
            id="rec_02",
            run_id="run_01",
            task_id="researcher",
            parent_task_id="planner",
            agent_id="http://localhost:9002",
            status=TaskStatus.FAILED,
            input_artifact_refs=["art_01"],
            output_artifact_refs=[],
            prompt="Search for X",
            model="gpt-4",
            tool_calls=[{"name": "search", "args": {"q": "test"}}],
            latency_ms=5000,
            trace_id="trace_01",
            error="Timeout exceeded",
        )
        assert er.status == TaskStatus.FAILED
        assert er.error == "Timeout exceeded"
        assert er.tool_calls is not None


class TestRunSummary:
    def test_create_minimal(self) -> None:
        rs = RunSummary(
            run_id="run_01",
            workflow_name="test-workflow",
            status="completed",
            total_nodes=5,
        )
        assert rs.completed_nodes == 0
        assert rs.failed_nodes == 0
        assert rs.forked_from is None
        assert rs.forked_at_step is None
        assert rs.completed_at is None
        assert rs.started_at.tzinfo == UTC

    def test_replay_run(self) -> None:
        rs = RunSummary(
            run_id="run_02",
            workflow_name="test-workflow",
            status="completed",
            total_nodes=5,
            completed_nodes=5,
            forked_from="run_01",
            forked_at_step="validator",
        )
        assert rs.forked_from == "run_01"
        assert rs.forked_at_step == "validator"
