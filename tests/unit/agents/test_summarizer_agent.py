"""Tests for summarizer reference agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from binex.agents.summarizer.agent import SummarizerAgent
from binex.agents.summarizer.app import app
from binex.models.artifact import Artifact, Lineage


def _make_artifact(content, art_type="validated_results") -> Artifact:
    return Artifact(
        id="art_test01",
        run_id="run_01",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="validator"),
    )


class TestSummarizerAgent:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value=json.dumps({
                "title": "WiFi CSI Research Report",
                "summary": "An overview of WiFi CSI sensing.",
                "sections": [
                    {"heading": "Background", "content": "WiFi CSI uses..."},
                    {"heading": "Applications", "content": "Used for..."},
                ],
                "sources": ["Paper A", "Paper B"],
            })
        )
        return client

    @pytest.fixture
    def agent(self, mock_client: AsyncMock) -> SummarizerAgent:
        return SummarizerAgent(client=mock_client)

    async def test_execute_produces_report(self, agent: SummarizerAgent) -> None:
        artifacts = [
            _make_artifact({
                "validated_findings": ["Finding 1", "Finding 2"],
                "duplicates_removed": 1,
                "confidence_scores": {"Finding 1": 0.9},
            })
        ]
        results = await agent.execute("task_01", "run_01", artifacts)

        assert len(results) == 1
        assert results[0].type == "research_report"
        assert results[0].content["title"] == "WiFi CSI Research Report"
        assert len(results[0].content["sections"]) == 2
        assert results[0].content["sources"] == ["Paper A", "Paper B"]

    async def test_extract_findings_fallback(self, agent: SummarizerAgent) -> None:
        artifacts = [_make_artifact("raw content", "text")]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].type == "research_report"

    async def test_parse_report_fallback(self, agent: SummarizerAgent) -> None:
        agent._client.complete_json = AsyncMock(return_value="plain text report")
        artifacts = [_make_artifact({"validated_findings": ["F1"]})]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].content["title"] == "Research Report"
        assert results[0].content["summary"] == "plain text report"


class TestSummarizerApp:
    async def test_health_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["agent"] == "summarizer"

    async def test_cancel_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/cancel", json={"task_id": "t1"})
            assert resp.status_code == 200
