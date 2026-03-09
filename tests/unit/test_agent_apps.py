"""Tests for the FastAPI endpoints in researcher, summarizer, and validator agent apps."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from binex.models.artifact import Artifact, Lineage


# ---------------------------------------------------------------------------
# Researcher
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_researcher_health():
    from binex.agents.researcher.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "agent": "researcher"}


@pytest.mark.asyncio
async def test_researcher_execute_with_artifacts():
    from binex.agents.researcher.app import app

    mock_result = Artifact(
        id="out1",
        run_id="run_1",
        type="result",
        content="research output",
        lineage=Lineage(produced_by="researcher", derived_from=[]),
    )

    with patch("binex.agents.researcher.app._agent") as mock_agent:
        mock_agent.execute = AsyncMock(return_value=[mock_result])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                json={
                    "task_id": "t1",
                    "run_id": "run_1",
                    "artifacts": [
                        {"id": "a1", "type": "input", "content": "hello"},
                    ],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "artifacts": [{"id": "out1", "type": "result", "content": "research output"}]
    }
    mock_agent.execute.assert_awaited_once()
    call_args = mock_agent.execute.call_args
    assert call_args[0][0] == "t1"
    assert call_args[0][1] == "run_1"
    assert len(call_args[0][2]) == 1
    assert call_args[0][2][0].id == "a1"


@pytest.mark.asyncio
async def test_researcher_execute_empty_artifacts():
    from binex.agents.researcher.app import app

    with patch("binex.agents.researcher.app._agent") as mock_agent:
        mock_agent.execute = AsyncMock(return_value=[])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/execute", json={})

    assert resp.status_code == 200
    assert resp.json() == {"artifacts": []}
    call_args = mock_agent.execute.call_args
    assert call_args[0][0] == "unknown"  # default task_id
    assert call_args[0][1].startswith("run_")  # auto-generated run_id
    assert call_args[0][2] == []  # no input artifacts


@pytest.mark.asyncio
async def test_researcher_cancel():
    from binex.agents.researcher.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/cancel", json={"task_id": "t1"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "acknowledged"}


# ---------------------------------------------------------------------------
# Summarizer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarizer_health():
    from binex.agents.summarizer.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "agent": "summarizer"}


@pytest.mark.asyncio
async def test_summarizer_execute_with_artifacts():
    from binex.agents.summarizer.app import app

    mock_result = Artifact(
        id="out2",
        run_id="run_2",
        type="summary",
        content="summary output",
        lineage=Lineage(produced_by="summarizer", derived_from=[]),
    )

    with patch("binex.agents.summarizer.app._agent") as mock_agent:
        mock_agent.execute = AsyncMock(return_value=[mock_result])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                json={
                    "task_id": "t2",
                    "run_id": "run_2",
                    "artifacts": [
                        {"id": "a2", "type": "input", "content": "summarize this"},
                    ],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "artifacts": [{"id": "out2", "type": "summary", "content": "summary output"}]
    }
    mock_agent.execute.assert_awaited_once()
    call_args = mock_agent.execute.call_args
    assert call_args[0][0] == "t2"
    assert call_args[0][1] == "run_2"
    assert len(call_args[0][2]) == 1
    assert call_args[0][2][0].id == "a2"


@pytest.mark.asyncio
async def test_summarizer_execute_empty_artifacts():
    from binex.agents.summarizer.app import app

    with patch("binex.agents.summarizer.app._agent") as mock_agent:
        mock_agent.execute = AsyncMock(return_value=[])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/execute", json={})

    assert resp.status_code == 200
    assert resp.json() == {"artifacts": []}
    call_args = mock_agent.execute.call_args
    assert call_args[0][0] == "unknown"
    assert call_args[0][1].startswith("run_")
    assert call_args[0][2] == []


@pytest.mark.asyncio
async def test_summarizer_cancel():
    from binex.agents.summarizer.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/cancel", json={"task_id": "t2"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "acknowledged"}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validator_health():
    from binex.agents.validator.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "agent": "validator"}


@pytest.mark.asyncio
async def test_validator_execute_with_artifacts():
    from binex.agents.validator.app import app

    mock_result = Artifact(
        id="out3",
        run_id="run_3",
        type="validation",
        content="validation output",
        lineage=Lineage(produced_by="validator", derived_from=[]),
    )

    with patch("binex.agents.validator.app._agent") as mock_agent:
        mock_agent.execute = AsyncMock(return_value=[mock_result])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/execute",
                json={
                    "task_id": "t3",
                    "run_id": "run_3",
                    "artifacts": [
                        {"id": "a3", "type": "input", "content": "validate this"},
                    ],
                },
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "artifacts": [
            {"id": "out3", "type": "validation", "content": "validation output"}
        ]
    }
    mock_agent.execute.assert_awaited_once()
    call_args = mock_agent.execute.call_args
    assert call_args[0][0] == "t3"
    assert call_args[0][1] == "run_3"
    assert len(call_args[0][2]) == 1
    assert call_args[0][2][0].id == "a3"


@pytest.mark.asyncio
async def test_validator_execute_empty_artifacts():
    from binex.agents.validator.app import app

    with patch("binex.agents.validator.app._agent") as mock_agent:
        mock_agent.execute = AsyncMock(return_value=[])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/execute", json={})

    assert resp.status_code == 200
    assert resp.json() == {"artifacts": []}
    call_args = mock_agent.execute.call_args
    assert call_args[0][0] == "unknown"
    assert call_args[0][1].startswith("run_")
    assert call_args[0][2] == []


@pytest.mark.asyncio
async def test_validator_cancel():
    from binex.agents.validator.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/cancel", json={"task_id": "t3"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "acknowledged"}
