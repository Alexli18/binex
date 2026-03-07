"""LocalPythonAdapter — executes agent logic in-process as a Python callable."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact
from binex.models.task import TaskNode

HandlerType = Callable[
    [TaskNode, list[Artifact]],
    Coroutine[Any, Any, list[Artifact]],
]


class LocalPythonAdapter:
    """Adapter that runs agent logic as an in-process async callable."""

    def __init__(self, handler: HandlerType) -> None:
        self._handler = handler

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        return await self._handler(task, input_artifacts)

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
