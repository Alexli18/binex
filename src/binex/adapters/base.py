"""AgentAdapter protocol — interface all agent backends must implement."""

from __future__ import annotations

from typing import Protocol

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact
from binex.models.task import TaskNode


class AgentAdapter(Protocol):
    """Protocol for agent execution backends."""

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        """Dispatch a task to an agent and return output artifacts."""
        ...

    async def cancel(self, task_id: str) -> None:
        """Cancel a running task (best-effort)."""
        ...

    async def health(self) -> AgentHealth:
        """Return the current health status of the agent."""
        ...
