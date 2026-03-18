"""LocalPythonAdapter — executes agent logic in-process as a Python callable.

LocalShellAdapter — executes shell commands specified via ``local://command``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode

logger = logging.getLogger(__name__)

HandlerType = Callable[
    [TaskNode, list[Artifact]],
    Coroutine[Any, Any, list[Artifact]],
]

# Timeout for shell commands (seconds).
_SHELL_TIMEOUT = 30
# Max output size (bytes) to capture from shell.
_SHELL_MAX_OUTPUT = 10 * 1024


class LocalPythonAdapter:
    """Adapter that runs agent logic as an in-process async callable."""

    def __init__(self, handler: HandlerType) -> None:
        self._handler = handler

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        artifacts = await self._handler(task, input_artifacts)
        return ExecutionResult(artifacts=artifacts)

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


class LocalShellAdapter:
    """Adapter that runs a shell command specified in the agent URI.

    ``local://echo hello`` executes ``echo hello`` as a shell process.
    stdout is captured as artifact content (parsed as JSON if valid).
    Input artifacts are passed via the ``BINEX_INPUT`` environment variable
    as a JSON string.
    """

    def __init__(self, command: str, *, timeout: int = _SHELL_TIMEOUT) -> None:
        self._command = command
        self._timeout = timeout

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        env_input = json.dumps(
            {a.id: a.content for a in input_artifacts} if input_artifacts else {}
        )

        try:
            proc = await asyncio.create_subprocess_shell(
                self._command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"BINEX_INPUT": env_input},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout,
            )
        except TimeoutError:
            proc.kill()
            raise RuntimeError(
                f"local:// command timed out after {self._timeout}s: {self._command}"
            ) from None

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()[:_SHELL_MAX_OUTPUT]
            raise RuntimeError(
                f"local:// command failed (exit {proc.returncode}): "
                f"{self._command}\n{err_msg}"
            )

        raw_output = stdout.decode(errors="replace").strip()[:_SHELL_MAX_OUTPUT]

        # Try to parse as JSON, fallback to plain string
        try:
            content = json.loads(raw_output)
        except (json.JSONDecodeError, ValueError):
            content = raw_output

        artifact = Artifact(
            id=f"art_{task.node_id}",
            run_id=task.run_id,
            type="result",
            content=content,
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in input_artifacts],
            ),
        )
        return ExecutionResult(artifacts=[artifact])

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
