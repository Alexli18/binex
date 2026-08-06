"""Tests for the scheduler API endpoints (status, history, start/stop, add/remove)."""

from __future__ import annotations

import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import binex.ui.api.scheduler as scheduler_api
from binex.scheduler.models import HistoryEntry, ScheduledWorkflow, SchedulerState
from binex.scheduler.state import load_state, save_state


@pytest.fixture(autouse=True)
def _reset_scheduler_process():
    # _scheduler_process is module-global mutable state; without a reset a
    # mock left behind by one test leaks "already_running" into the next.
    scheduler_api._scheduler_process = None
    yield
    scheduler_api._scheduler_process = None


@pytest.fixture
def state_path(tmp_path):
    path = tmp_path / "scheduler.json"
    with patch("binex.ui.api.scheduler._get_state_path", return_value=path):
        yield path


def _mock_proc(pid: int = 4242, alive: bool = True) -> MagicMock:
    # spec=Popen so a typo'd method name raises instead of being silently
    # swallowed; pid is an instance attribute (absent from the class spec)
    # and must be assigned explicitly.
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = pid
    proc.poll.return_value = None if alive else 0
    proc.wait.return_value = 0
    return proc


def _entry(workflow: str, day: int) -> HistoryEntry:
    return HistoryEntry(
        workflow=workflow,
        timestamp=datetime(2026, 1, day, tzinfo=UTC),
        run_id=f"sched-{workflow}-{day}",
        status="completed",
        duration_s=1.5,
        cost=0.01,
    )


# ---------------------------------------------------------------------------
# /scheduler/status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_not_running(client, state_path):
    save_state(SchedulerState(registered=["/tmp/a.yaml"]), state_path)
    wf = ScheduledWorkflow(
        name="nightly",
        path="/tmp/a.yaml",
        schedule="0 2 * * *",
        next_run=datetime(2026, 1, 2, 2, 0, tzinfo=UTC),
    )
    with patch("binex.ui.api.scheduler.scan_directory", return_value=[wf]):
        resp = await client.get("/api/v1/scheduler/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    assert data["pid"] is None
    assert data["registered_count"] == 1
    assert data["workflows"] == [
        {
            "name": "nightly",
            "path": "/tmp/a.yaml",
            "schedule": "0 2 * * *",
            "next_run": "2026-01-02T02:00:00+00:00",
        }
    ]


@pytest.mark.asyncio
async def test_status_running(client, state_path):
    scheduler_api._scheduler_process = _mock_proc(pid=4242)
    with patch("binex.ui.api.scheduler.scan_directory", return_value=[]):
        resp = await client.get("/api/v1/scheduler/status")

    data = resp.json()
    assert data["running"] is True
    assert data["pid"] == 4242


# ---------------------------------------------------------------------------
# /scheduler/history
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_limit_returns_newest_first(client, state_path):
    state = SchedulerState()
    for day in (1, 2, 3):
        state.add_history(_entry("wf", day))
    save_state(state, state_path)

    resp = await client.get("/api/v1/scheduler/history", params={"limit": 2})

    assert resp.status_code == 200
    history = resp.json()["history"]
    assert [e["run_id"] for e in history] == ["sched-wf-3", "sched-wf-2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 1001])
async def test_history_invalid_limit_rejected(client, state_path, limit):
    resp = await client.get("/api/v1/scheduler/history", params={"limit": limit})

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /scheduler/start, /scheduler/stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_spawns_subprocess(client, state_path):
    # Build the proc mock before patching: once Popen is patched,
    # spec=subprocess.Popen would spec against the mock (InvalidSpecError).
    proc = _mock_proc(pid=555)
    with patch("binex.ui.api.scheduler.subprocess.Popen", return_value=proc) as popen:
        resp = await client.post("/api/v1/scheduler/start", json={"directory": "."})

    assert resp.status_code == 200
    assert resp.json() == {"status": "started", "pid": 555}
    assert popen.call_count == 1


@pytest.mark.asyncio
async def test_start_twice_reports_already_running(client, state_path):
    proc = _mock_proc(pid=555)
    with patch("binex.ui.api.scheduler.subprocess.Popen", return_value=proc) as popen:
        first = await client.post("/api/v1/scheduler/start", json={"directory": "."})
        second = await client.post("/api/v1/scheduler/start", json={"directory": "."})

    assert first.json()["status"] == "started"
    assert second.json() == {"status": "already_running", "pid": 555}
    assert popen.call_count == 1


@pytest.mark.asyncio
async def test_stop_without_running_scheduler(client, state_path):
    resp = await client.post("/api/v1/scheduler/stop")

    assert resp.status_code == 200
    assert resp.json() == {"status": "not_running"}


@pytest.mark.asyncio
async def test_stop_sends_sigint_and_waits(client, state_path):
    proc = _mock_proc(pid=777)
    scheduler_api._scheduler_process = proc

    resp = await client.post("/api/v1/scheduler/stop")

    assert resp.json() == {"status": "stopped", "pid": 777}
    proc.send_signal.assert_called_once_with(signal.SIGINT)
    proc.wait.assert_called_once_with(timeout=30)
    assert scheduler_api._scheduler_process is None


# ---------------------------------------------------------------------------
# /scheduler/add, /scheduler/remove
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_registers_workflow(client, state_path, tmp_path):
    wf_path = tmp_path / "wf.yaml"

    resp = await client.post(
        "/api/v1/scheduler/add", json={"workflow_path": str(wf_path)}
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "registered", "path": str(wf_path.resolve())}
    assert load_state(state_path).registered == [str(wf_path.resolve())]


@pytest.mark.asyncio
async def test_add_is_idempotent(client, state_path, tmp_path):
    wf_path = str(tmp_path / "wf.yaml")

    await client.post("/api/v1/scheduler/add", json={"workflow_path": wf_path})
    await client.post("/api/v1/scheduler/add", json={"workflow_path": wf_path})

    assert load_state(state_path).registered == [str(Path(wf_path).resolve())]


@pytest.mark.asyncio
async def test_remove_registered_workflow(client, state_path, tmp_path):
    wf_path = str((tmp_path / "wf.yaml").resolve())
    save_state(SchedulerState(registered=[wf_path]), state_path)

    resp = await client.post(
        "/api/v1/scheduler/remove", json={"workflow_path": wf_path}
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "removed", "path": wf_path}
    assert load_state(state_path).registered == []


@pytest.mark.asyncio
async def test_remove_unknown_workflow_returns_404(client, state_path, tmp_path):
    resp = await client.post(
        "/api/v1/scheduler/remove",
        json={"workflow_path": str(tmp_path / "ghost.yaml")},
    )

    assert resp.status_code == 404
    assert resp.json()["status"] == "not_found"
