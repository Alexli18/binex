"""PlannerAgent — decomposes a research query into subtasks via LLM."""

from __future__ import annotations

import json
import uuid

from binex.agents.common.llm_client import LLMClient
from binex.models.artifact import Artifact, Lineage

SYSTEM_PROMPT = (
    "You are a research planner. Decompose the given research query into "
    "2-4 specific subtasks that can be researched independently. "
    "Return a JSON array of subtask strings. No extra text."
)


class PlannerAgent:
    """Reference agent that creates an execution plan from a research query."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()

    async def execute(
        self,
        task_id: str,
        run_id: str,
        input_artifacts: list[Artifact],
    ) -> list[Artifact]:
        query = self._extract_query(input_artifacts)
        raw = await self._client.complete_json(
            f"Research query: {query}",
            system=SYSTEM_PROMPT,
        )
        subtasks = self._parse_subtasks(raw)

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                type="execution_plan",
                content={"query": query, "subtasks": subtasks},
                lineage=Lineage(
                    produced_by=task_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

    def _extract_query(self, artifacts: list[Artifact]) -> str:
        for art in artifacts:
            if isinstance(art.content, str):
                return art.content
            if isinstance(art.content, dict) and "query" in art.content:
                return art.content["query"]
        return ""

    def _parse_subtasks(self, raw: str) -> list[str]:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(s) for s in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return [line.strip() for line in raw.strip().splitlines() if line.strip()]
