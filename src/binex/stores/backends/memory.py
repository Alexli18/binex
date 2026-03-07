"""In-memory store backends for testing."""

from __future__ import annotations

from binex.models.artifact import Artifact
from binex.models.execution import ExecutionRecord, RunSummary


class InMemoryArtifactStore:
    """In-memory artifact store for tests."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    async def store(self, artifact: Artifact) -> None:
        self._artifacts[artifact.id] = artifact

    async def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.run_id == run_id]

    async def get_lineage(self, artifact_id: str) -> list[Artifact]:
        result: list[Artifact] = []
        visited: set[str] = set()
        queue = [artifact_id]
        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)
            art = self._artifacts.get(current_id)
            if art is None:
                continue
            if current_id != artifact_id:
                result.append(art)
            queue.extend(art.lineage.derived_from)
        return result


class InMemoryExecutionStore:
    """In-memory execution store for tests."""

    def __init__(self) -> None:
        self._runs: dict[str, RunSummary] = {}
        self._records: list[ExecutionRecord] = []

    async def close(self) -> None:
        pass

    async def record(self, execution_record: ExecutionRecord) -> None:
        self._records.append(execution_record)

    async def get_run(self, run_id: str) -> RunSummary | None:
        return self._runs.get(run_id)

    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None:
        for rec in self._records:
            if rec.run_id == run_id and rec.task_id == task_id:
                return rec
        return None

    async def list_runs(self) -> list[RunSummary]:
        return list(self._runs.values())

    async def create_run(self, run_summary: RunSummary) -> None:
        self._runs[run_summary.run_id] = run_summary

    async def update_run(self, run_summary: RunSummary) -> None:
        self._runs[run_summary.run_id] = run_summary

    async def list_records(self, run_id: str) -> list[ExecutionRecord]:
        return [r for r in self._records if r.run_id == run_id]


__all__ = [
    "InMemoryArtifactStore",
    "InMemoryExecutionStore",
]
