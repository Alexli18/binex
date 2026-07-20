"""Node cache entry model."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    """A reusable node result, keyed by a content hash of the node's inputs."""

    cache_key: str
    run_id: str  # the run that first produced this result
    node_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    saved_cost: float = 0.0  # cost of the original execution (reported on hit)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


__all__ = ["CacheEntry"]
