"""Tests for trace timeline generation (T035)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryExecutionStore
from binex.trace.tracer import generate_timeline, generate_timeline_json


@pytest.fixture
def execution_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def run_id() -> str:
    return "run_001"


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 3, 7, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
async def populated_store(
    execution_store: InMemoryExecutionStore,
    run_id: str,
    base_time: datetime,
) -> InMemoryExecutionStore:
    summary = RunSummary(
        run_id=run_id,
        workflow_name="test-pipeline",
        status="completed",
        started_at=base_time,
        completed_at=base_time + timedelta(seconds=5),
        total_nodes=3,
        completed_nodes=3,
    )
    await execution_store.create_run(summary)

    records = [
        ExecutionRecord(
            id="rec_1",
            run_id=run_id,
            task_id="planner",
            agent_id="local://planner",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=[],
            output_artifact_refs=["art_plan"],
            latency_ms=1200,
            timestamp=base_time,
            trace_id="trace_001",
        ),
        ExecutionRecord(
            id="rec_2",
            run_id=run_id,
            task_id="researcher",
            agent_id="local://researcher",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=["art_plan"],
            output_artifact_refs=["art_research"],
            latency_ms=2500,
            timestamp=base_time + timedelta(seconds=1),
            trace_id="trace_001",
        ),
        ExecutionRecord(
            id="rec_3",
            run_id=run_id,
            task_id="summarizer",
            agent_id="local://summarizer",
            status=TaskStatus.FAILED,
            input_artifact_refs=["art_research"],
            output_artifact_refs=[],
            latency_ms=800,
            timestamp=base_time + timedelta(seconds=3),
            trace_id="trace_001",
            error="LLM timeout",
        ),
    ]
    for rec in records:
        await execution_store.record(rec)

    return execution_store


@pytest.mark.asyncio
async def test_generate_timeline_returns_formatted_string(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline(populated_store, run_id)
    assert isinstance(result, str)
    assert "planner" in result
    assert "researcher" in result
    assert "summarizer" in result


@pytest.mark.asyncio
async def test_generate_timeline_shows_status(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline(populated_store, run_id)
    assert "completed" in result.lower()
    assert "failed" in result.lower()


@pytest.mark.asyncio
async def test_generate_timeline_shows_latency(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline(populated_store, run_id)
    assert "1200" in result or "1.2" in result
    assert "2500" in result or "2.5" in result


@pytest.mark.asyncio
async def test_generate_timeline_shows_agent(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline(populated_store, run_id)
    assert "local://planner" in result
    assert "local://researcher" in result


@pytest.mark.asyncio
async def test_generate_timeline_shows_error_for_failed(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline(populated_store, run_id)
    assert "LLM timeout" in result


@pytest.mark.asyncio
async def test_generate_timeline_shows_artifact_refs(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline(populated_store, run_id)
    assert "art_plan" in result
    assert "art_research" in result


@pytest.mark.asyncio
async def test_generate_timeline_json_returns_list(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline_json(populated_store, run_id)
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0]["task_id"] == "planner"
    assert result[0]["status"] == "completed"
    assert result[0]["latency_ms"] == 1200


@pytest.mark.asyncio
async def test_generate_timeline_nonexistent_run(
    execution_store: InMemoryExecutionStore,
) -> None:
    result = await generate_timeline(execution_store, "nonexistent")
    assert "no records" in result.lower() or result.strip() == ""


@pytest.mark.asyncio
async def test_generate_timeline_records_ordered_by_timestamp(
    populated_store: InMemoryExecutionStore, run_id: str
) -> None:
    result = await generate_timeline_json(populated_store, run_id)
    timestamps = [r["timestamp"] for r in result]
    assert timestamps == sorted(timestamps)
