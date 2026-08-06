"""Tests for the CAO adapter API endpoints.

Covers health, server lifecycle, profiles, sessions, and HITL input.
"""

from __future__ import annotations

import signal
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

import binex.ui.api.cao as cao_api
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

CAO_URL = "http://cao.test"


@pytest.fixture(autouse=True)
def _cao_env(monkeypatch, tmp_path):
    # Settings() is re-read in every handler; pointing the server URL at a
    # fake host makes respx routes unambiguous and guarantees no test can
    # accidentally talk to a real CAO server on localhost:9889.
    monkeypatch.setenv("BINEX_CAO_SERVER_URL", CAO_URL)
    monkeypatch.setenv("BINEX_CAO_AGENT_STORE", str(tmp_path / "agent-store"))


@pytest.fixture(autouse=True)
def _reset_cao_process():
    cao_api._cao_process = None
    yield
    cao_api._cao_process = None


def _mock_proc(pid: int = 9001, alive: bool = True) -> MagicMock:
    # spec=Popen catches typo'd method names; pid is an instance attribute
    # (absent from the class spec) and must be assigned explicitly.
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = pid
    proc.poll.return_value = None if alive else 1
    proc.wait.return_value = 0
    return proc


# ---------------------------------------------------------------------------
# GET /cao/health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_health_online(client):
    route = respx.get(f"{CAO_URL}/health").mock(return_value=httpx.Response(200))

    resp = await client.get("/api/v1/cao/health")

    assert resp.json() == {"status": "online", "server_url": CAO_URL}
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_health_degraded_on_non_200(client):
    respx.get(f"{CAO_URL}/health").mock(return_value=httpx.Response(500))

    resp = await client.get("/api/v1/cao/health")

    assert resp.json() == {
        "status": "degraded",
        "server_url": CAO_URL,
        "http_status": 500,
    }


@pytest.mark.asyncio
@respx.mock
async def test_health_offline_on_connect_error(client):
    respx.get(f"{CAO_URL}/health").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    resp = await client.get("/api/v1/cao/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "offline", "server_url": CAO_URL}


# ---------------------------------------------------------------------------
# POST /cao/server/start, /cao/server/stop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_start_with_own_process_alive(client):
    # Own subprocess alive → early return, no HTTP probe, no new Popen.
    cao_api._cao_process = _mock_proc(pid=9001)

    resp = await client.post("/api/v1/cao/server/start")

    assert resp.json() == {"status": "already_running", "pid": 9001}


@pytest.mark.asyncio
@respx.mock
async def test_server_start_detects_external_server(client):
    respx.get(f"{CAO_URL}/health").mock(return_value=httpx.Response(200))

    resp = await client.post("/api/v1/cao/server/start")

    assert resp.json() == {
        "status": "already_running",
        "message": "CAO server is already running externally",
    }


@pytest.mark.asyncio
@respx.mock
async def test_server_start_binary_missing(client):
    respx.get(f"{CAO_URL}/health").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with patch("binex.ui.api.cao.shutil.which", return_value=None):
        resp = await client.post("/api/v1/cao/server/start")

    assert resp.status_code == 400
    assert "cao-server not found" in resp.json()["error"]


@pytest.mark.asyncio
@respx.mock
async def test_server_start_success(client):
    respx.get(f"{CAO_URL}/health").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    proc = _mock_proc(pid=9002)

    with (
        patch("binex.ui.api.cao.shutil.which", return_value="/usr/bin/cao-server"),
        patch("binex.ui.api.cao.subprocess.Popen", return_value=proc) as popen,
        patch("asyncio.sleep", new_callable=AsyncMock),  # skip the 1s startup wait
    ):
        resp = await client.post("/api/v1/cao/server/start")

    assert resp.json() == {"status": "started", "pid": 9002}
    assert popen.call_args[0][0] == ["/usr/bin/cao-server"]


@pytest.mark.asyncio
@respx.mock
async def test_server_start_reports_immediate_death(client):
    respx.get(f"{CAO_URL}/health").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    proc = _mock_proc(pid=9003, alive=False)

    with (
        patch("binex.ui.api.cao.shutil.which", return_value="/usr/bin/cao-server"),
        patch("binex.ui.api.cao.subprocess.Popen", return_value=proc),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        resp = await client.post("/api/v1/cao/server/start")

    assert resp.status_code == 500
    assert resp.json() == {"error": "CAO server failed to start"}
    assert cao_api._cao_process is None


@pytest.mark.asyncio
async def test_server_stop_not_managed(client):
    resp = await client.post("/api/v1/cao/server/stop")

    assert resp.json() == {"status": "not_managed"}


@pytest.mark.asyncio
async def test_server_stop_sends_sigint(client):
    proc = _mock_proc(pid=9004)
    cao_api._cao_process = proc

    resp = await client.post("/api/v1/cao/server/stop")

    assert resp.json() == {"status": "stopped", "pid": 9004}
    proc.send_signal.assert_called_once_with(signal.SIGINT)
    proc.wait.assert_called_once_with(timeout=10)
    assert cao_api._cao_process is None


# ---------------------------------------------------------------------------
# GET /cao/profiles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profiles_missing_store_dir_warns(client, tmp_path):
    resp = await client.get("/api/v1/cao/profiles")

    assert resp.status_code == 200
    data = resp.json()
    assert data["profiles"] == []
    assert "not found" in data["warning"]


@pytest.mark.asyncio
async def test_profiles_lists_md_stems_sorted(client, tmp_path):
    store_dir = tmp_path / "agent-store"
    store_dir.mkdir()
    (store_dir / "reviewer.md").write_text("# reviewer")
    (store_dir / "architect.md").write_text("# architect")
    (store_dir / "notes.txt").write_text("ignored")

    resp = await client.get("/api/v1/cao/profiles")

    data = resp.json()
    assert data["profiles"] == ["architect", "reviewer"]
    assert "warning" not in data


# ---------------------------------------------------------------------------
# GET /cao/sessions, DELETE /cao/sessions/{terminal_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions(client):
    exec_store = InMemoryExecutionStore()
    await exec_store.create_cao_session("term-1", "run-1", "node-a")

    with patch(
        "binex.ui.api.cao._get_stores",
        return_value=(exec_store, InMemoryArtifactStore()),
    ):
        resp = await client.get("/api/v1/cao/sessions")

    sessions = resp.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["terminal_id"] == "term-1"


@pytest.mark.asyncio
@respx.mock
async def test_delete_session_cleans_up_even_if_cao_is_down(client):
    # Best-effort contract: the CAO server being unreachable must not stop
    # registry cleanup.
    respx.post(f"{CAO_URL}/terminals/term-1/exit").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    respx.delete(f"{CAO_URL}/terminals/term-1").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    exec_store = InMemoryExecutionStore()
    await exec_store.create_cao_session("term-1", "run-1", "node-a")

    with patch(
        "binex.ui.api.cao._get_stores",
        return_value=(exec_store, InMemoryArtifactStore()),
    ):
        resp = await client.delete("/api/v1/cao/sessions/term-1")

    assert resp.json() == {"ok": True}
    assert await exec_store.get_cao_sessions() == []


@pytest.mark.asyncio
@respx.mock
async def test_delete_unknown_session_returns_404(client):
    respx.post(f"{CAO_URL}/terminals/ghost/exit").mock(
        return_value=httpx.Response(200)
    )
    respx.delete(f"{CAO_URL}/terminals/ghost").mock(
        return_value=httpx.Response(200)
    )

    with patch(
        "binex.ui.api.cao._get_stores",
        return_value=(InMemoryExecutionStore(), InMemoryArtifactStore()),
    ):
        resp = await client.delete("/api/v1/cao/sessions/ghost")

    assert resp.status_code == 404
    assert resp.json() == {"error": "session not found"}


# ---------------------------------------------------------------------------
# POST /cao/terminals/{terminal_id}/input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_terminal_input_forwarded(client):
    route = respx.post(f"{CAO_URL}/terminals/term-1/input").mock(
        return_value=httpx.Response(200)
    )

    resp = await client.post(
        "/api/v1/cao/terminals/term-1/input", json={"message": "yes, proceed"}
    )

    assert resp.json() == {"ok": True}
    assert route.calls.last.request.url.params["message"] == "yes, proceed"


@pytest.mark.asyncio
@respx.mock
async def test_terminal_input_cao_down_returns_502(client):
    respx.post(f"{CAO_URL}/terminals/term-1/input").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    resp = await client.post(
        "/api/v1/cao/terminals/term-1/input", json={"message": "hello"}
    )

    assert resp.status_code == 502
    assert "CAO server error" in resp.json()["error"]
