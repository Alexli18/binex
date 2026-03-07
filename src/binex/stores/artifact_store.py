"""ArtifactStore protocol — interface for artifact persistence."""

from __future__ import annotations

from typing import Protocol

from binex.models.artifact import Artifact


class ArtifactStore(Protocol):
    """Protocol for storing and retrieving artifacts."""

    async def store(self, artifact: Artifact) -> None:
        """Persist an artifact."""
        ...

    async def get(self, artifact_id: str) -> Artifact | None:
        """Retrieve an artifact by ID."""
        ...

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        """List all artifacts for a given run."""
        ...

    async def get_lineage(self, artifact_id: str) -> list[Artifact]:
        """Walk the derived_from chain and return all ancestor artifacts."""
        ...


__all__ = ["ArtifactStore"]
