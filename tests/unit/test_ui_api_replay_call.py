"""Tests for the observed-call replay API endpoint (#74 UI)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from binex.observer import CapturedCall, flush_observed_run
from binex.ui.server import create_app


@pytest.fixture(autouse=True)
def _store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # replay_call + flush both use get_stores() → BINEX_STORE_PATH, so a shared
    # temp store means no patching is needed.
    monkeypatch.setenv("BINEX_STORE_PATH", str(tmp_path / ".binex"))


@pytest.fixture
async def client():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_replay_call_endpoint(client) -> None:
    run_id = await flush_observed_run("crew", [
        CapturedCall("gpt-4o", [{"role": "user", "content": "plan"}],
                     "original plan", 10, 20, 0.003, 500),
    ])
    resp = await client.post(
        f"/api/v1/runs/{run_id}/calls/call_000/replay",
        json={"model": "gpt-4o-mini", "mock_response": "a fresh plan"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_response"] == "original plan"
    assert data["replay_response"] == "a fresh plan"
    assert data["replay_model"] == "gpt-4o-mini"
    assert data["changed"] is True


@pytest.mark.asyncio
async def test_replay_call_endpoint_unknown(client) -> None:
    resp = await client.post(
        "/api/v1/runs/obs_nope/calls/call_000/replay",
        json={"mock_response": "x"},
    )
    assert resp.status_code == 404
    assert "error" in resp.json()
