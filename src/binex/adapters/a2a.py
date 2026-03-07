"""A2AAgentAdapter — communicates with A2A-compatible agents via HTTP."""

from __future__ import annotations

import uuid

import httpx

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


class A2AAgentAdapter:
    """Adapter for remote A2A-compatible agents."""

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint.rstrip("/")

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        payload = {
            "task_id": task.id,
            "skill": task.skill,
            "trace_id": trace_id,
            "artifacts": [
                {"id": a.id, "type": a.type, "content": a.content}
                for a in input_artifacts
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._endpoint}/execute",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type=art_data.get("type", "unknown"),
                content=art_data.get("content"),
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
            for art_data in data.get("artifacts", [])
        ]

    async def cancel(self, task_id: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._endpoint}/cancel",
                json={"task_id": task_id},
                timeout=10.0,
            )

    async def health(self) -> AgentHealth:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._endpoint}/health",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return AgentHealth.ALIVE
                return AgentHealth.DEGRADED
        except Exception:
            return AgentHealth.DOWN
