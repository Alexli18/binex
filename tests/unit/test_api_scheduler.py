"""Tests for scheduler API endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from binex.scheduler.models import SchedulerState
from binex.scheduler.state import save_state


@pytest.fixture
def client(tmp_path: Path):
    """Create a test client with isolated state path."""
    state_path = tmp_path / "scheduler.json"

    with (
        patch("binex.ui.api.scheduler._get_state_path", return_value=state_path),
        patch("binex.ui.api.scheduler.scan_directory", return_value=[]),
        patch("binex.ui.api.scheduler._scheduler_process", None),
    ):
        from fastapi import FastAPI

        from binex.ui.api.scheduler import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        yield TestClient(app)


class TestSchedulerStatus:
    def test_status_not_running(self, client):
        resp = client.get("/api/v1/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False
        assert data["pid"] is None
        assert data["workflows"] == []

    def test_status_with_workflows(self, tmp_path: Path):
        from datetime import UTC, datetime

        from binex.scheduler.models import ScheduledWorkflow

        state_path = tmp_path / "scheduler.json"
        wf = ScheduledWorkflow(
            name="test-wf",
            path="/tmp/test.yaml",
            schedule="*/5 * * * *",
            next_run=datetime.now(UTC),
        )

        with (
            patch("binex.ui.api.scheduler._get_state_path", return_value=state_path),
            patch("binex.ui.api.scheduler.scan_directory", return_value=[wf]),
            patch("binex.ui.api.scheduler._scheduler_process", None),
        ):
            from fastapi import FastAPI

            from binex.ui.api.scheduler import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.get("/api/v1/scheduler/status")
            data = resp.json()
            assert len(data["workflows"]) == 1
            assert data["workflows"][0]["name"] == "test-wf"


class TestSchedulerHistory:
    def test_history_empty(self, client):
        resp = client.get("/api/v1/scheduler/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["history"] == []

    def test_history_with_entries(self, tmp_path: Path):
        from binex.scheduler.state import record_run

        state_path = tmp_path / "scheduler.json"
        state = SchedulerState()
        record_run(state, "wf1", "run-1", "completed", 1.0, 0.01)
        save_state(state, state_path)

        with (
            patch("binex.ui.api.scheduler._get_state_path", return_value=state_path),
            patch("binex.ui.api.scheduler.scan_directory", return_value=[]),
            patch("binex.ui.api.scheduler._scheduler_process", None),
        ):
            from fastapi import FastAPI

            from binex.ui.api.scheduler import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.get("/api/v1/scheduler/history")
            data = resp.json()
            assert len(data["history"]) == 1
            assert data["history"][0]["status"] == "completed"


class TestSchedulerStop:
    def test_stop_not_running(self, client):
        resp = client.post("/api/v1/scheduler/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_running"


class TestSchedulerAddRemove:
    def test_add_workflow(self, tmp_path: Path):
        state_path = tmp_path / "scheduler.json"
        wf_path = tmp_path / "test.yaml"
        wf_path.write_text("name: test\nnodes: {}")

        with (
            patch("binex.ui.api.scheduler._get_state_path", return_value=state_path),
            patch("binex.ui.api.scheduler.scan_directory", return_value=[]),
            patch("binex.ui.api.scheduler._scheduler_process", None),
        ):
            from fastapi import FastAPI

            from binex.ui.api.scheduler import router

            app = FastAPI()
            app.include_router(router, prefix="/api/v1")
            client = TestClient(app)

            resp = client.post(
                "/api/v1/scheduler/add",
                json={"workflow_path": str(wf_path)},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "registered"

    def test_remove_not_found(self, client):
        resp = client.post(
            "/api/v1/scheduler/remove",
            json={"workflow_path": "/nonexistent.yaml"},
        )
        assert resp.status_code == 404
        assert resp.json()["status"] == "not_found"
