"""Tests for src/binex/ui/api/eval.py (T015, T018)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from binex.eval.models import EvalCaseResult, EvalResult
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_result(suite_name: str = "my-suite", result_id: str = "eval_abc123") -> dict:
    from datetime import UTC, datetime
    r = EvalResult(
        suite_name=suite_name,
        suite_path="/path/suite.yaml",
        executed_at=datetime.now(UTC),
        total=2,
        passed=1,
        failed=1,
        no_baseline=0,
        total_cost=0.01,
        cases=[
            EvalCaseResult(case_id="c1", verdict="pass", run_id="run_a"),
            EvalCaseResult(case_id="c2", verdict="fail", run_id="run_b"),
        ],
    )
    return {
        "id": result_id,
        "suite_name": r.suite_name,
        "executed_at": r.executed_at.isoformat(),
        "total": r.total,
        "passed": r.passed,
        "failed": r.failed,
        "no_baseline": r.no_baseline,
        "total_cost": r.total_cost,
        "payload": r.model_dump_json(),
    }


@pytest.fixture
def client():
    from binex.ui.api.eval import router
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    es = InMemoryExecutionStore()
    ats = InMemoryArtifactStore()
    with patch("binex.ui.api.eval._get_stores", return_value=(es, ats)):
        with TestClient(app) as c:
            yield c, es, ats


class TestEvalExecutionsEndpoint:
    def test_list_executions_empty(self, client):
        c, es, ats = client
        resp = c.get("/api/v1/eval/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert "executions" in data
        assert data["executions"] == []

    def test_list_executions_with_data(self, client):
        c, es, ats = client
        row = _make_result()

        async def _mock_list(limit=50, suite_name=None):
            return [row]

        with patch.object(es, "list_eval_results", side_effect=_mock_list):
            resp = c.get("/api/v1/eval/executions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["executions"]) == 1
        assert data["executions"][0]["suite_name"] == "my-suite"

    def test_filter_by_suite(self, client):
        c, es, ats = client
        row = _make_result(suite_name="other-suite")

        async def _mock_list(limit=50, suite_name=None):
            if suite_name and suite_name != "other-suite":
                return []
            return [row]

        with patch.object(es, "list_eval_results", side_effect=_mock_list):
            resp = c.get("/api/v1/eval/executions?suite=other-suite")
        assert resp.status_code == 200
        assert len(resp.json()["executions"]) == 1


class TestEvalExecutionDetailEndpoint:
    def test_get_execution_not_found(self, client):
        c, es, ats = client
        resp = c.get("/api/v1/eval/executions/eval_notexist")
        assert resp.status_code == 404

    def test_get_execution_found(self, client):
        c, es, ats = client
        row = _make_result(result_id="eval_abc123")

        async def _mock_get(result_id):
            if result_id == "eval_abc123":
                return row
            return None

        with patch.object(es, "get_eval_result", side_effect=_mock_get):
            resp = c.get("/api/v1/eval/executions/eval_abc123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suite_name"] == "my-suite"
        assert "cases" in data


class TestEvalBaselinesEndpoint:
    def test_get_baselines_empty(self, client):
        c, es, ats = client
        resp = c.get("/api/v1/eval/baselines?suite=my-suite")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suite"] == "my-suite"
        assert data["baselines"] == []

    def test_get_baselines_with_data(self, client):
        c, es, ats = client

        async def _mock_baselines(suite_name):
            return {"c1": "run_abc"}

        with patch.object(es, "get_baselines", side_effect=_mock_baselines):
            resp = c.get("/api/v1/eval/baselines?suite=my-suite")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["baselines"]) == 1
        assert data["baselines"][0]["case_id"] == "c1"
        assert data["baselines"][0]["run_id"] == "run_abc"
