"""Binex persistence layer — store protocols and factory functions."""

from binex.stores.artifact_store import ArtifactStore
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore
from binex.stores.execution_store import ExecutionStore


def create_artifact_store(
    backend: str = "filesystem", **kwargs: str,
) -> InMemoryArtifactStore | FilesystemArtifactStore:
    """Create an artifact store instance.

    Args:
        backend: "memory" or "filesystem" (default).
        **kwargs: Backend-specific options (e.g., base_path for filesystem).
    """
    if backend == "memory":
        return InMemoryArtifactStore()
    if backend == "filesystem":
        base_path = kwargs.get("base_path", ".binex/artifacts")
        return FilesystemArtifactStore(base_path=base_path)
    raise ValueError(f"Unknown artifact store backend: {backend}")


def create_execution_store(
    backend: str = "sqlite", **kwargs: str,
) -> InMemoryExecutionStore | SqliteExecutionStore:
    """Create an execution store instance.

    Args:
        backend: "memory" or "sqlite" (default).
        **kwargs: Backend-specific options (e.g., db_path for sqlite).
    """
    if backend == "memory":
        return InMemoryExecutionStore()
    if backend == "sqlite":
        db_path = kwargs.get("db_path", ".binex/binex.db")
        return SqliteExecutionStore(db_path=db_path)
    raise ValueError(f"Unknown execution store backend: {backend}")


__all__ = [
    "ArtifactStore",
    "ExecutionStore",
    "create_artifact_store",
    "create_execution_store",
]
