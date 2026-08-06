"""Tests for the gateway API endpoints (subprocess start/stop/process-status)."""

from __future__ import annotations

import signal
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import binex.ui.api.gateway as gateway_api


@pytest.fixture(autouse=True)
def _reset_gateway_process():
    gateway_api._gateway_process = None
    yield
    gateway_api._gateway_process = None


def _mock_proc(pid: int = 8421, alive: bool = True) -> MagicMock:
    # spec=Popen catches typo'd method names; pid is an instance attribute
    # (absent from the class spec) and must be assigned explicitly.
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = pid
    proc.poll.return_value = None if alive else 0
    proc.wait.return_value = 0
    return proc


@pytest.mark.asyncio
async def test_process_status_not_running(client):
    resp = await client.get("/api/v1/gateway/process-status")

    assert resp.status_code == 200
    assert resp.json() == {"running": False, "pid": None}


@pytest.mark.asyncio
async def test_process_status_running(client):
    gateway_api._gateway_process = _mock_proc(pid=8421)

    resp = await client.get("/api/v1/gateway/process-status")

    assert resp.json() == {"running": True, "pid": 8421}


@pytest.mark.asyncio
async def test_start_spawns_subprocess_with_options(client):
    proc = _mock_proc(pid=321)
    with patch(
        "binex.ui.api.gateway.subprocess.Popen", return_value=proc
    ) as popen:
        resp = await client.post(
            "/api/v1/gateway/start",
            json={"config": "gw.yaml", "host": "0.0.0.0", "port": 9000},
        )

    assert resp.json() == {"status": "started", "pid": 321}
    assert popen.call_args[0][0] == [
        sys.executable, "-m", "binex", "gateway",
        "--config", "gw.yaml", "--host", "0.0.0.0", "--port", "9000",
    ]


@pytest.mark.asyncio
async def test_start_twice_reports_already_running(client):
    proc = _mock_proc(pid=321)
    with patch(
        "binex.ui.api.gateway.subprocess.Popen", return_value=proc
    ) as popen:
        first = await client.post("/api/v1/gateway/start", json={})
        second = await client.post("/api/v1/gateway/start", json={})

    assert first.json()["status"] == "started"
    assert second.json() == {"status": "already_running", "pid": 321}
    assert popen.call_count == 1


@pytest.mark.asyncio
async def test_stop_without_running_gateway(client):
    resp = await client.post("/api/v1/gateway/stop")

    assert resp.status_code == 200
    assert resp.json() == {"status": "not_running"}


@pytest.mark.asyncio
async def test_stop_sends_sigint_and_waits(client):
    proc = _mock_proc(pid=654)
    gateway_api._gateway_process = proc

    resp = await client.post("/api/v1/gateway/stop")

    assert resp.json() == {"status": "stopped", "pid": 654}
    proc.send_signal.assert_called_once_with(signal.SIGINT)
    proc.wait.assert_called_once_with(timeout=30)
    assert gateway_api._gateway_process is None
