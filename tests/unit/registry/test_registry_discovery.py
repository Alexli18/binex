"""Tests for agent discovery/crawling module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from binex.registry.discovery import AgentDiscovery, DiscoveryError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_AGENT_CARD = {
    "name": "test-agent",
    "capabilities": ["summarize", "translate"],
    "url": "http://agent.example.com",
    "version": "1.0",
}


def _mock_response(*, status_code: int = 200, json_data: dict | None = None, text: str = ""):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("Invalid JSON")
        resp.text = text
    return resp


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def discovery(mock_client: AsyncMock) -> AgentDiscovery:
    return AgentDiscovery(client=mock_client)


# ---------------------------------------------------------------------------
# fetch_agent_card
# ---------------------------------------------------------------------------


class TestFetchAgentCard:
    async def test_successful_fetch(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(json_data=SAMPLE_AGENT_CARD)

        card = await discovery.fetch_agent_card("http://agent.example.com")

        mock_client.get.assert_awaited_once_with(
            "http://agent.example.com/.well-known/agent.json",
            timeout=pytest.approx(10.0, abs=5),
        )
        assert card == SAMPLE_AGENT_CARD

    async def test_fetch_strips_trailing_slash(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(json_data=SAMPLE_AGENT_CARD)

        await discovery.fetch_agent_card("http://agent.example.com/")

        url_called = mock_client.get.call_args[0][0]
        assert "//." not in url_called
        assert url_called.endswith("/.well-known/agent.json")

    async def test_fetch_network_error_raises_discovery_error(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.side_effect = httpx.ConnectError("connection refused")

        with pytest.raises(DiscoveryError, match="connection refused"):
            await discovery.fetch_agent_card("http://agent.example.com")

    async def test_fetch_timeout_raises_discovery_error(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(DiscoveryError, match="timed out"):
            await discovery.fetch_agent_card("http://agent.example.com")

    async def test_fetch_http_error_raises_discovery_error(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(status_code=404)

        with pytest.raises(DiscoveryError):
            await discovery.fetch_agent_card("http://agent.example.com")

    async def test_fetch_invalid_json_raises_discovery_error(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(text="<html>not json</html>")

        with pytest.raises(DiscoveryError, match="Invalid JSON"):
            await discovery.fetch_agent_card("http://agent.example.com")


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


class TestDiscover:
    async def test_discover_creates_agent_info(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(json_data=SAMPLE_AGENT_CARD)

        agent = await discovery.discover("http://agent.example.com")

        assert agent.name == "test-agent"
        assert agent.endpoint == "http://agent.example.com"
        assert set(agent.capabilities) == {"summarize", "translate"}
        assert agent.agent_card == SAMPLE_AGENT_CARD
        assert agent.id  # must be non-empty

    async def test_discover_generates_deterministic_id(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(json_data=SAMPLE_AGENT_CARD)

        agent1 = await discovery.discover("http://agent.example.com")
        agent2 = await discovery.discover("http://agent.example.com")

        assert agent1.id == agent2.id

    async def test_discover_different_endpoints_get_different_ids(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.return_value = _mock_response(json_data=SAMPLE_AGENT_CARD)

        agent1 = await discovery.discover("http://agent1.example.com")
        agent2 = await discovery.discover("http://agent2.example.com")

        assert agent1.id != agent2.id

    async def test_discover_handles_missing_capabilities(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        card = {"name": "minimal-agent", "url": "http://minimal.example.com"}
        mock_client.get.return_value = _mock_response(json_data=card)

        agent = await discovery.discover("http://minimal.example.com")

        assert agent.name == "minimal-agent"
        assert agent.capabilities == []

    async def test_discover_propagates_discovery_error(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        mock_client.get.side_effect = httpx.ConnectError("refused")

        with pytest.raises(DiscoveryError):
            await discovery.discover("http://agent.example.com")


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    async def test_refresh_updates_capabilities(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        from binex.models.agent import AgentInfo

        old_agent = AgentInfo(
            id="abc",
            endpoint="http://agent.example.com",
            name="old-name",
            capabilities=["old-cap"],
            agent_card={"name": "old-name", "capabilities": ["old-cap"]},
        )

        updated_card = {
            "name": "new-name",
            "capabilities": ["new-cap-a", "new-cap-b"],
            "url": "http://agent.example.com",
        }
        mock_client.get.return_value = _mock_response(json_data=updated_card)

        before = datetime.now(UTC)
        refreshed = await discovery.refresh(old_agent)

        assert refreshed.id == old_agent.id
        assert refreshed.endpoint == old_agent.endpoint
        assert refreshed.capabilities == ["new-cap-a", "new-cap-b"]
        assert refreshed.agent_card == updated_card
        assert refreshed.last_seen >= before

    async def test_refresh_updates_name(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        from binex.models.agent import AgentInfo

        old_agent = AgentInfo(
            id="abc",
            endpoint="http://agent.example.com",
            name="old-name",
            capabilities=[],
            agent_card={},
        )

        updated_card = {"name": "updated-name", "capabilities": [], "url": "http://agent.example.com"}
        mock_client.get.return_value = _mock_response(json_data=updated_card)

        refreshed = await discovery.refresh(old_agent)
        assert refreshed.name == "updated-name"

    async def test_refresh_propagates_error(
        self, discovery: AgentDiscovery, mock_client: AsyncMock
    ) -> None:
        from binex.models.agent import AgentInfo

        agent = AgentInfo(
            id="abc",
            endpoint="http://agent.example.com",
            name="test",
            capabilities=[],
            agent_card={},
        )
        mock_client.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(DiscoveryError):
            await discovery.refresh(agent)
