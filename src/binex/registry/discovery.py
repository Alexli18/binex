"""Agent discovery and crawling for the A2A registry."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import httpx

from binex.models.agent import AgentInfo

_AGENT_CARD_PATH = "/.well-known/agent.json"
_DEFAULT_TIMEOUT = 10.0


class DiscoveryError(Exception):
    """Raised when agent discovery fails."""


class AgentDiscovery:
    """Discovers and crawls A2A agent cards from remote endpoints."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_agent_card(self, endpoint: str) -> dict:
        """Fetch the agent card JSON from *endpoint*/.well-known/agent.json.

        Returns the parsed JSON dict.  Raises :class:`DiscoveryError` on any
        network, HTTP, or JSON-parsing failure.
        """
        url = endpoint.rstrip("/") + _AGENT_CARD_PATH
        try:
            response = await self._client.get(url, timeout=_DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPStatusError, httpx.HTTPError) as exc:
            raise DiscoveryError(str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise DiscoveryError(f"Invalid JSON from {url}: {exc}") from exc

    async def discover(self, endpoint: str) -> AgentInfo:
        """Discover an agent at *endpoint* and return an :class:`AgentInfo`."""
        card = await self.fetch_agent_card(endpoint)
        return AgentInfo(
            id=_endpoint_id(endpoint),
            endpoint=endpoint,
            name=card.get("name", "unknown"),
            capabilities=card.get("capabilities", []),
            agent_card=card,
        )

    async def refresh(self, agent: AgentInfo) -> AgentInfo:
        """Re-fetch the agent card for *agent* and return an updated copy."""
        card = await self.fetch_agent_card(agent.endpoint)
        return agent.model_copy(
            update={
                "name": card.get("name", agent.name),
                "capabilities": card.get("capabilities", []),
                "agent_card": card,
                "last_seen": datetime.now(UTC),
            }
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _endpoint_id(endpoint: str) -> str:
    """Generate a deterministic short ID from an endpoint URL."""
    return hashlib.sha256(endpoint.encode()).hexdigest()[:16]


__all__ = ["AgentDiscovery", "DiscoveryError"]
