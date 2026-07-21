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
        from binex.runtime.cost_report import CostReporter

        # Pass report_progress / report_cost only to handlers that opt in by
        # declaring them, so existing handlers keep working (#78, #79).
        kwargs: dict[str, Any] = {}
        if progress is not None and self._handler_accepts("report_progress"):
            kwargs["report_progress"] = progress.report
        cost_reporter: CostReporter | None = None
        if self._handler_accepts("report_cost"):
            cost_reporter = CostReporter(task)
            kwargs["report_cost"] = cost_reporter.report

        artifacts = await self._handler(task, input_artifacts, **kwargs)
        cost = cost_reporter.record if cost_reporter else None
        return ExecutionResult(artifacts=artifacts, cost=cost)

    def _handler_accepts(self, param: str) -> bool:
        import inspect

        try:
            return param in inspect.signature(self._handler).parameters
        except (ValueError, TypeError):
            return False

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
