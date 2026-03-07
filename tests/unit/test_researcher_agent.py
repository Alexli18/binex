"""Tests for researcher reference agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from binex.agents.researcher.agent import ResearcherAgent
from binex.agents.researcher.app import app
from binex.models.artifact import Artifact, Lineage


def _make_artifact(content, art_type="input") -> Artifact:
    return Artifact(
        id="art_test01",
        run_id="run_01",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="external"),
    )


class TestResearcherAgent:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value=json.dumps({
                "findings": ["Finding 1", "Finding 2"],
                "sources": ["Source A"],
            })
        )
        return client

    @pytest.fixture
    def agent(self, mock_client: AsyncMock) -> ResearcherAgent:
        return ResearcherAgent(client=mock_client)

    async def test_execute_produces_search_results(self, agent: ResearcherAgent) -> None:
        artifacts = [_make_artifact("WiFi CSI signal processing")]
        results = await agent.execute("task_01", "run_01", artifacts)

        assert len(results) == 1
        assert results[0].type == "search_results"
        assert results[0].content["query"] == "WiFi CSI signal processing"
        assert len(results[0].content["findings"]) == 2
        assert results[0].content["sources"] == ["Source A"]

    async def test_extract_query_from_plan(self, agent: ResearcherAgent) -> None:
        artifacts = [_make_artifact({"subtasks": ["subtask1", "subtask2"]})]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].content["query"] == "subtask1"

    async def test_parse_results_fallback(self, agent: ResearcherAgent) -> None:
        agent._client.complete_json = AsyncMock(return_value="raw text response")
        artifacts = [_make_artifact("query")]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].content["findings"] == ["raw text response"]
        assert results[0].content["sources"] == []


class TestResearcherApp:
    async def test_health_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["agent"] == "researcher"

    async def test_cancel_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/cancel", json={"task_id": "t1"})
            assert resp.status_code == 200
