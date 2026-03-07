"""Tests for validator reference agent."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from binex.agents.validator.agent import ValidatorAgent
from binex.agents.validator.app import app
from binex.models.artifact import Artifact, Lineage


def _make_artifact(content, art_type="search_results") -> Artifact:
    return Artifact(
        id="art_test01",
        run_id="run_01",
        type=art_type,
        content=content,
        lineage=Lineage(produced_by="researcher"),
    )


class TestValidatorAgent:
    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.complete_json = AsyncMock(
            return_value=json.dumps({
                "validated_findings": ["Valid finding 1", "Valid finding 2"],
                "duplicates_removed": 1,
                "confidence_scores": {"Valid finding 1": 0.9, "Valid finding 2": 0.8},
            })
        )
        return client

    @pytest.fixture
    def agent(self, mock_client: AsyncMock) -> ValidatorAgent:
        return ValidatorAgent(client=mock_client)

    async def test_execute_produces_validated_results(self, agent: ValidatorAgent) -> None:
        artifacts = [
            _make_artifact({"findings": ["F1", "F2"], "sources": ["S1"]}),
            _make_artifact({"findings": ["F2", "F3"], "sources": ["S2"]}),
        ]
        artifacts[1] = Artifact(
            id="art_test02", run_id="run_01", type="search_results",
            content={"findings": ["F2", "F3"], "sources": ["S2"]},
            lineage=Lineage(produced_by="researcher"),
        )

        results = await agent.execute("task_01", "run_01", artifacts)
        assert len(results) == 1
        assert results[0].type == "validated_results"
        assert results[0].content["duplicates_removed"] == 1
        assert len(results[0].content["validated_findings"]) == 2

    async def test_combine_findings_from_strings(self, agent: ValidatorAgent) -> None:
        artifacts = [_make_artifact("raw finding text", "text")]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].type == "validated_results"

    async def test_parse_validation_fallback(self, agent: ValidatorAgent) -> None:
        agent._client.complete_json = AsyncMock(return_value="not json")
        artifacts = [_make_artifact({"findings": ["F1"]})]
        results = await agent.execute("task_01", "run_01", artifacts)
        assert results[0].content["validated_findings"] == ["not json"]
        assert results[0].content["duplicates_removed"] == 0


class TestValidatorApp:
    async def test_health_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["agent"] == "validator"

    async def test_cancel_endpoint(self) -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/cancel", json={"task_id": "t1"})
            assert resp.status_code == 200
