"""Tests for SchedulerEngine._run_workflow — the actual execution path.

_tick/rescan/skip logic is covered in test_scheduler_engine.py; the start()
loop (signal handlers + sleep) is a conscious boundary. Here we pin what
happens when a due workflow actually runs: status mapping, cost recording,
and the exception contract (a crashing workflow records 'failed' and never
takes the scheduler down).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.execution import RunSummary
from binex.scheduler.engine import SchedulerEngine
from binex.scheduler.models import ScheduledWorkflow, SchedulerState
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _wf(name: str = "wf") -> ScheduledWorkflow:
    return ScheduledWorkflow(
        name=name,
        path="/tmp/wf.yaml",
        schedule="*/5 * * * *",
        next_run=datetime.now(UTC) - timedelta(minutes=1),
    )


def _engine(wf: ScheduledWorkflow) -> SchedulerEngine:
    return SchedulerEngine(workflows=[wf], state=SchedulerState())


def _summary(status: str, total_cost: float = 0.0) -> RunSummary:
    return RunSummary(
        run_id="run-1",
        workflow_name="wf",
        status=status,
        total_nodes=1,
        completed_nodes=1,
        total_cost=total_cost,
    )


def _patches(run_result=None, load_error=None):
    """Patch the function-local imports of _run_workflow."""
    orchestrator = MagicMock()
    orchestrator.run_workflow = AsyncMock(return_value=run_result)
    load = MagicMock(return_value=MagicMock(name="spec"))
    if load_error is not None:
        load.side_effect = load_error
    return (
        patch("binex.workflow_spec.loader.load_workflow", load),
        patch(
            "binex.cli.get_stores",
            return_value=(InMemoryExecutionStore(), InMemoryArtifactStore()),
        ),
        patch(
            "binex.runtime.orchestrator.Orchestrator",
            MagicMock(return_value=orchestrator),
        ),
    )


@pytest.mark.asyncio
async def test_completed_run_recorded_with_cost():
    wf = _wf()
    engine = _engine(wf)
    p_load, p_stores, p_orch = _patches(run_result=_summary("completed", total_cost=0.5))

    with p_load, p_stores, p_orch:
        await engine._run_workflow(wf)

    entry = engine.state.history[0]
    assert entry.workflow == "wf"
    assert entry.status == "completed"
    assert entry.cost == 0.5
    assert entry.run_id.startswith("sched-wf-")


@pytest.mark.asyncio
async def test_non_completed_status_mapped_to_failed():
    wf = _wf()
    engine = _engine(wf)
    p_load, p_stores, p_orch = _patches(run_result=_summary("over_budget"))

    with p_load, p_stores, p_orch:
        await engine._run_workflow(wf)

    assert engine.state.history[0].status == "failed"


@pytest.mark.asyncio
async def test_workflow_exception_recorded_as_failed_not_raised():
    wf = _wf()
    engine = _engine(wf)
    p_load, p_stores, p_orch = _patches(load_error=FileNotFoundError("wf.yaml gone"))

    with p_load, p_stores, p_orch:
        await engine._run_workflow(wf)  # must not raise

    entry = engine.state.history[0]
    assert entry.status == "failed"
    assert entry.cost is None
