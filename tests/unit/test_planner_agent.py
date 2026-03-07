"""Tests for planner reference agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from binex.agents.planner.agent import PlannerAgent
from binex.agents.planner.app import app
from binex.models.artifact import Artifact, Lineage


def _make_artifact(content, art_type="input") -> Artifact:
    return Artifact(
        id="art_test01",
        run_id="run_01",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="external"),
    )


class TestPlannerAgent:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value='["Subtask 1", "Subtask 2", "Subtask 3"]'
        )
        return client

    @pytest.fixture
    def agent(self, mock_client: AsyncMock) -> PlannerAgent:
        return PlannerAgent(client=mock_client)

    async def test_execute_produces_execution_plan(self, agent: PlannerAgent) -> None:
        artifacts = [_make_artifact("WiFi CSI sensing research")]
        results = await agent.execute("task_01", "run_01", artifacts)

        assert len(results) == 1
        assert results[0].type == "execution_plan"
        assert results[0].content["query"] == "WiFi CSI sensing research"
        assert len(results[0].content["subtasks"]) == 3
        assert results[0].lineage.produced_by == "task_01"
        assert results[0].lineage.derived_from == ["art_test01"]

    async def test_extract_query_from_dict(self, agent: PlannerAgent) -> None:
        artifacts = [_make_artifact({"query": "test query"})]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].content["query"] == "test query"

    async def test_parse_subtasks_fallback(self, agent: PlannerAgent) -> None:
        agent._client.complete_json = AsyncMock(return_value="not valid json\nline2")
        artifacts = [_make_artifact("query")]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert len(results[0].content["subtasks"]) == 2

    async def test_empty_artifacts(self, agent: PlannerAgent) -> None:
        results = await agent.execute("task_01", "run_01", [])
        assert results[0].content["query"] == ""


class TestPlannerApp:
    async def test_health_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
            assert resp.json()["agent"] == "planner"

    async def test_cancel_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/cancel", json={"task_id": "t1"})
            assert resp.status_code == 200

    async def test_execute_endpoint(self) -> None:
        import binex.agents.planner.app as planner_app

        mock_client = AsyncMock()
        mock_client.complete_json = AsyncMock(return_value='["subtask1", "subtask2"]')
        original_agent = planner_app._agent
        planner_app._agent = PlannerAgent(client=mock_client)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/execute", json={
                    "task_id": "t1",
                    "artifacts": [{"id": "a1", "type": "input", "content": "test query"}],
                })
                assert resp.status_code == 200
                data = resp.json()
                assert "artifacts" in data
        finally:
            planner_app._agent = original_agent
