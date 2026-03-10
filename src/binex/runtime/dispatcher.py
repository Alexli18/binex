"""Task dispatcher — resolves adapters, handles retries and deadlines."""

from __future__ import annotations

import asyncio

from binex.adapters.base import AgentAdapter
from binex.models.artifact import Artifact
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


class Dispatcher:
    """Dispatches tasks to the appropriate agent adapter with retry and timeout."""

    def __init__(self) -> None:
        self._adapters: dict[str, AgentAdapter] = {}

    def register_adapter(self, agent_key: str, adapter: AgentAdapter) -> None:
        self._adapters[agent_key] = adapter

    def get_adapter(self, agent_key: str) -> AgentAdapter:
        if agent_key not in self._adapters:
            raise KeyError(f"No adapter registered for '{agent_key}'")
        return self._adapters[agent_key]

    async def dispatch(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        adapter = self.get_adapter(task.agent)
        max_retries = task.retry_policy.max_retries if task.retry_policy else 1
        backoff = task.retry_policy.backoff if task.retry_policy else "exponential"
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                if task.deadline_ms:
                    timeout = task.deadline_ms / 1000.0
                    result = await asyncio.wait_for(
                        adapter.execute(task, input_artifacts, trace_id),
                        timeout=timeout,
                    )
                else:
                    result = await adapter.execute(task, input_artifacts, trace_id)

                # Handle both ExecutionResult and legacy list[Artifact] returns
                if isinstance(result, ExecutionResult):
                    return result
                return ExecutionResult(artifacts=result)
            except TimeoutError:
                raise
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    delay = _backoff_delay(attempt, backoff)
                    await asyncio.sleep(delay)

        raise last_error  # type: ignore[misc]


def _backoff_delay(attempt: int, strategy: str) -> float:
    if strategy == "exponential":
        return min(2 ** (attempt - 1) * 0.1, 10.0)
    return 0.1  # fixed
