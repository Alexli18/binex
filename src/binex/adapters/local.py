"""LocalPythonAdapter — executes agent logic in-process as a Python callable."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode

HandlerType = Callable[..., Coroutine[Any, Any, list[Artifact]]]


class LocalPythonAdapter:
    """Adapter that runs agent logic as an in-process async callable."""

    def __init__(self, handler: HandlerType) -> None:
        self._handler = handler

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
        *,
        progress: Any | None = None,
    ) -> ExecutionResult:
        # Pass report_progress only to handlers that opt in by declaring it,
        # so existing two-arg handlers keep working (issue #78).
        if progress is not None and self._handler_wants_progress():
            artifacts = await self._handler(
                task, input_artifacts, report_progress=progress.report,
            )
        else:
            artifacts = await self._handler(task, input_artifacts)
        return ExecutionResult(artifacts=artifacts)

    def _handler_wants_progress(self) -> bool:
        import inspect

        try:
            return "report_progress" in inspect.signature(self._handler).parameters
        except (ValueError, TypeError):
            return False

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
