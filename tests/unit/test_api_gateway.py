"""Tests for gateway API endpoints — start, stop, process-status."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from binex.ui.api.gateway import router


@pytest.fixture
def client():
    """Create a test client with gateway process reset."""
    with patch("binex.ui.api.gateway._gateway_process", None):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        yield TestClient(app)


class TestGatewayStart:
    def test_start_launches_subprocess(self):
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None

        with (
            patch("binex.ui.api.gateway._gateway_process", None),
            patch("binex.ui.api.gateway.subprocess.Popen", return_value=mock_proc) as mock_popen,
        ):
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.post("/api/v1/gateway/start", json={})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "started"
            assert data["pid"] == 12345
            mock_popen.assert_called_once()

    def test_start_with_config_options(self):
        mock_proc = MagicMock()
        mock_proc.pid = 99
        mock_proc.poll.return_value = None

        with (
            patch("binex.ui.api.gateway._gateway_process", None),
            patch("binex.ui.api.gateway.subprocess.Popen", return_value=mock_proc) as mock_popen,
        ):
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.post("/api/v1/gateway/start", json={
                "config": "gw.yaml",
                "host": "0.0.0.0",
                "port": 9000,
            })
            assert resp.status_code == 200

            cmd = mock_popen.call_args[0][0]
            assert "--config" in cmd
            assert "gw.yaml" in cmd
            assert "--host" in cmd
            assert "0.0.0.0" in cmd
            assert "--port" in cmd
            assert "9000" in cmd

    def test_start_already_running(self):
        mock_proc = MagicMock()
        mock_proc.pid = 555
        mock_proc.poll.return_value = None  # still running

        with patch("binex.ui.api.gateway._gateway_process", mock_proc):
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.post("/api/v1/gateway/start", json={})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "already_running"
            assert data["pid"] == 555


class TestGatewayStop:
    def test_stop_not_running(self, client):
        resp = client.post("/api/v1/gateway/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_running"

    def test_stop_running_process(self):
        mock_proc = MagicMock()
        mock_proc.pid = 777
        mock_proc.poll.return_value = None  # running
        mock_proc.wait.return_value = 0

        with patch("binex.ui.api.gateway._gateway_process", mock_proc):
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.post("/api/v1/gateway/stop")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "stopped"
            assert data["pid"] == 777
            mock_proc.send_signal.assert_called_once()

    def test_stop_already_exited(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # already exited

        with patch("binex.ui.api.gateway._gateway_process", mock_proc):
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.post("/api/v1/gateway/stop")
            assert resp.status_code == 200
            assert resp.json()["status"] == "not_running"


class TestGatewayProcessStatus:
    def test_not_running(self, client):
        resp = client.get("/api/v1/gateway/process-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False
        assert data["pid"] is None

    def test_running(self):
        mock_proc = MagicMock()
        mock_proc.pid = 333
        mock_proc.poll.return_value = None

        with patch("binex.ui.api.gateway._gateway_process", mock_proc):
            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.get("/api/v1/gateway/process-status")
            data = resp.json()
            assert data["running"] is True
            assert data["pid"] == 333
