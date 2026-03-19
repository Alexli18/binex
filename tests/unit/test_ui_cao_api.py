"""Tests for CAO UI API endpoints (profiles, sessions, delete, terminal input)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from binex.ui.server import create_app


@pytest.fixture()
def client():
    app = create_app(dev=True)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /cao/profiles
# ---------------------------------------------------------------------------

class TestListProfiles:
    def test_profiles_with_files(self, client, tmp_path):
        store = tmp_path / "agent-store"
        store.mkdir()
        (store / "code_supervisor.md").write_text("# Agent")
        (store / "reviewer.md").write_text("# Agent")
        (store / "notes.txt").write_text("not a profile")

        with patch("binex.ui.api.cao.Settings") as mock_settings:
            mock_settings.return_value.cao_agent_store_dir = str(store)
            resp = client.get("/api/v1/cao/profiles")

        assert resp.status_code == 200
        data = resp.json()
        assert set(data["profiles"]) == {"code_supervisor", "reviewer"}
        assert data["agent_store_dir"] == str(store)
        assert "warning" not in data

    def test_profiles_missing_dir(self, client):
        with patch("binex.ui.api.cao.Settings") as mock_settings:
            mock_settings.return_value.cao_agent_store_dir = "/nonexistent/path"
            resp = client.get("/api/v1/cao/profiles")

        assert resp.status_code == 200
        data = resp.json()
        assert data["profiles"] == []
        assert "warning" in data
        assert "not found" in data["warning"]

    def test_profiles_empty_dir(self, client, tmp_path):
        store = tmp_path / "empty-store"
        store.mkdir()

        with patch("binex.ui.api.cao.Settings") as mock_settings:
            mock_settings.return_value.cao_agent_store_dir = str(store)
            resp = client.get("/api/v1/cao/profiles")

        assert resp.status_code == 200
        assert resp.json()["profiles"] == []


# ---------------------------------------------------------------------------
# GET /cao/sessions
# ---------------------------------------------------------------------------

class TestListSessions:
    def test_list_sessions(self, client):
        mock_store = AsyncMock()
        mock_store.get_cao_sessions = AsyncMock(return_value=[
            {
                "terminal_id": "term_1",
                "run_id": "run_a",
                "node_name": "review",
                "started_at": "2026-03-19T10:00:00",
                "status": "orphaned",
            },
        ])

        with patch("binex.ui.api.cao._get_stores", return_value=(mock_store, None)):
            resp = client.get("/api/v1/cao/sessions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["terminal_id"] == "term_1"
        mock_store.close.assert_awaited_once()

    def test_list_sessions_empty(self, client):
        mock_store = AsyncMock()
        mock_store.get_cao_sessions = AsyncMock(return_value=[])

        with patch("binex.ui.api.cao._get_stores", return_value=(mock_store, None)):
            resp = client.get("/api/v1/cao/sessions")

        assert resp.status_code == 200
        assert resp.json()["sessions"] == []


# ---------------------------------------------------------------------------
# DELETE /cao/sessions/{terminal_id}
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_delete_existing_session(self, client):
        mock_store = AsyncMock()
        mock_store.delete_cao_session = AsyncMock(return_value=True)

        with patch("binex.ui.api.cao._get_stores", return_value=(mock_store, None)):
            with patch("binex.ui.api.cao.Settings") as mock_settings:
                mock_settings.return_value.cao_server_url = "http://localhost:9889"
                with patch("binex.ui.api.cao.httpx.AsyncClient") as mock_http:
                    mock_client = AsyncMock()
                    mock_http.return_value.__aenter__ = AsyncMock(
                        return_value=mock_client,
                    )
                    mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                    resp = client.delete("/api/v1/cao/sessions/term_1")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock_store.delete_cao_session.assert_awaited_once_with("term_1")
        mock_store.close.assert_awaited_once()

    def test_delete_nonexistent_session(self, client):
        mock_store = AsyncMock()
        mock_store.delete_cao_session = AsyncMock(return_value=False)

        with patch("binex.ui.api.cao._get_stores", return_value=(mock_store, None)):
            with patch("binex.ui.api.cao.Settings") as mock_settings:
                mock_settings.return_value.cao_server_url = "http://localhost:9889"
                with patch("binex.ui.api.cao.httpx.AsyncClient") as mock_http:
                    mock_client = AsyncMock()
                    mock_http.return_value.__aenter__ = AsyncMock(
                        return_value=mock_client,
                    )
                    mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                    resp = client.delete("/api/v1/cao/sessions/nonexistent")

        assert resp.status_code == 404
        assert resp.json() == {"error": "session not found"}


# ---------------------------------------------------------------------------
# POST /cao/terminals/{terminal_id}/input
# ---------------------------------------------------------------------------

class TestSendTerminalInput:
    def test_send_input_success(self, client):
        """POST /cao/terminals/{id}/input forwards to CAO server."""
        with patch("binex.ui.api.cao.Settings") as mock_settings:
            mock_settings.return_value.cao_server_url = "http://localhost:9889"
            with patch("binex.ui.api.cao.httpx.AsyncClient") as mock_http:
                mock_async_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.raise_for_status = lambda: None
                mock_async_client.post = AsyncMock(return_value=mock_response)
                mock_http.return_value.__aenter__ = AsyncMock(
                    return_value=mock_async_client,
                )
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post(
                    "/api/v1/cao/terminals/term_42/input",
                    json={"message": "yes"},
                )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock_async_client.post.assert_awaited_once_with(
            "http://localhost:9889/terminals/term_42/input",
            data={"message": "yes"},
        )

    def test_send_input_cao_unavailable(self, client):
        """Returns 502 when CAO server is unavailable."""
        with patch("binex.ui.api.cao.Settings") as mock_settings:
            mock_settings.return_value.cao_server_url = "http://localhost:9889"
            with patch("binex.ui.api.cao.httpx.AsyncClient") as mock_http:
                mock_async_client = AsyncMock()
                mock_async_client.post = AsyncMock(
                    side_effect=httpx.ConnectError("Connection refused"),
                )
                mock_http.return_value.__aenter__ = AsyncMock(
                    return_value=mock_async_client,
                )
                mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = client.post(
                    "/api/v1/cao/terminals/term_42/input",
                    json={"message": "yes"},
                )

        assert resp.status_code == 502
        assert "CAO server error" in resp.json()["error"]
