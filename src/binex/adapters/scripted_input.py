"""ScriptedInputAdapter — non-interactive replacement for HumanInputAdapter."""

from __future__ import annotations

from uuid import uuid4

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


class ScriptedInputAdapter:
    """Returns preset values instead of calling click.prompt.

    Used by the eval runner and the MCP run_workflow tool to drive
    ``human://`` nodes non-interactively.

    Resolution order:
    1. ``inputs[task.node_id]`` — exact node-id match.
    2. Single-entry ``inputs`` when the workflow has exactly one human node
       (unnamed fallback).
    3. ``ValueError`` if no value can be resolved.
    """

    def __init__(self, inputs: dict[str, str]) -> None:
        self._inputs = inputs

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        value = self._resolve(task.node_id)
        artifact = Artifact(
            id=f"art_{uuid4().hex[:12]}",
            run_id=task.run_id,
            type="human_input",
            content=value,
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in input_artifacts],
            ),
        )
        return ExecutionResult(artifacts=[artifact])

    def _resolve(self, node_id: str) -> str:
        if node_id in self._inputs:
            return self._inputs[node_id]
        if len(self._inputs) == 1:
            return next(iter(self._inputs.values()))
        raise ValueError(
            f"ScriptedInputAdapter: no preset value for node '{node_id}'. "
            f"Available keys: {list(self._inputs.keys())}"
        )

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


__all__ = ["ScriptedInputAdapter"]
