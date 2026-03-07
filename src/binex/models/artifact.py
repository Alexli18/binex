"""Artifact, ArtifactRef, and Lineage domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Lineage(BaseModel):
    """Provenance metadata for an artifact."""

    produced_by: str
    derived_from: list[str] = Field(default_factory=list)


class Artifact(BaseModel):
    """A typed output produced by a task node."""

    id: str
    run_id: str
    type: str
    content: Any = None
    status: Literal["complete", "partial"] = "complete"
    lineage: Lineage
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactRef(BaseModel):
    """Lightweight reference to an artifact."""

    artifact_id: str
    type: str


__all__ = ["Artifact", "ArtifactRef", "Lineage"]
