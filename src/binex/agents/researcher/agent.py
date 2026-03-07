"""ResearcherAgent — searches sources for information on a subtask."""

from __future__ import annotations

import json
import uuid

from binex.agents.common.llm_client import LLMClient
from binex.models.artifact import Artifact, Lineage

SYSTEM_PROMPT = (
    "You are a research agent. Given a research subtask, provide detailed findings. "
    "Return a JSON object with 'findings' (array of finding strings) and "
    "'sources' (array of source references). No extra text."
)


class ResearcherAgent:
    """Reference agent that researches a given subtask."""

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
            f"Research subtask: {query}",
            system=SYSTEM_PROMPT,
        )
        content = self._parse_results(raw, query)

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                type="search_results",
                content=content,
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
            if isinstance(art.content, dict):
                if "query" in art.content:
                    return art.content["query"]
                if "subtasks" in art.content:
                    subtasks = art.content["subtasks"]
                    return subtasks[0] if subtasks else ""
        return ""

    def _parse_results(self, raw: str, query: str) -> dict:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {
                    "query": query,
                    "findings": parsed.get("findings", []),
                    "sources": parsed.get("sources", []),
                }
        except (json.JSONDecodeError, TypeError):
            pass
        return {"query": query, "findings": [raw.strip()], "sources": []}
