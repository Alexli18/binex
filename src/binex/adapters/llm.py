"""LLMAdapter — direct LLM calls via litellm."""

from __future__ import annotations

import uuid

import litellm

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


class LLMAdapter:
    """Adapter for direct LLM calls without an agent server."""

    def __init__(self, model: str, prompt_template: str | None = None) -> None:
        self._model = model
        self._prompt_template = prompt_template

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        prompt = self._build_prompt(task, input_artifacts)
        response = await litellm.acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type="llm_response",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

    def _build_prompt(self, task: TaskNode, input_artifacts: list[Artifact]) -> str:
        if self._prompt_template:
            return self._prompt_template

        parts: list[str] = []
        if task.skill:
            parts.append(f"Task: {task.skill}")
        for art in input_artifacts:
            parts.append(f"Input ({art.type}): {art.content}")
        return "\n".join(parts) if parts else "No input provided."

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
