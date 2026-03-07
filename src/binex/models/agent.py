"""AgentInfo and AgentHealth domain models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentHealth(enum.StrEnum):
    """Health status of an agent."""

    ALIVE = "alive"
    SLOW = "slow"
    DEGRADED = "degraded"
    DOWN = "down"


class AgentInfo(BaseModel):
    """Registry entry for a discovered agent."""

    id: str
    endpoint: str
    name: str
    capabilities: list[str] = Field(default_factory=list)
    health: AgentHealth = AgentHealth.ALIVE
    latency_avg_ms: int = 0
    last_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_card: dict[str, Any] = Field(default_factory=dict)


__all__ = ["AgentHealth", "AgentInfo"]
