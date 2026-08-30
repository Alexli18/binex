"""AgentAdapter protocol — interface all agent backends must implement."""

from __future__ import annotations

from typing import Protocol

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode

# Agent URI schemes handled by built-in adapters. Single source of truth: the
# dispatch table in `cli.adapter_registry` and the prefixes `PluginRegistry`
# reserves from plugins are both derived from this. They used to be separate
# literal lists and drifted — `cao` was dispatched but not reserved, so a plugin
# could claim `cao://` and be silently shadowed.
BUILTIN_AGENT_PREFIXES: frozenset[str] = frozenset(
    {"local", "llm", "human", "a2a", "cao"}
)


class AgentAdapter(Protocol):
    """Protocol for agent execution backends."""

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact] | ExecutionResult:
        """Dispatch a task to an agent and return output artifacts or ExecutionResult."""
        ...

    async def cancel(self, task_id: str) -> None:
        """Cancel a running task (best-effort)."""
        ...

    async def health(self) -> AgentHealth:
        """Return the current health status of the agent."""
        ...
