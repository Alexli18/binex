"""SummarizerAgent — produces a structured research report from validated findings."""

from __future__ import annotations

import json
import uuid

from binex.agents.common.llm_client import LLMClient
from binex.models.artifact import Artifact, Lineage

SYSTEM_PROMPT = (
    "You are a research summarizer. Given validated research findings, "
    "produce a structured report. Return JSON with 'title' (string), "
    "'summary' (string), 'sections' (array of objects with 'heading' and "
    "'content' fields), and 'sources' (array of strings). No extra text."
)


class SummarizerAgent:
    """Reference agent that produces a final research report."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()

    async def execute(
        self,
        task_id: str,
        run_id: str,
        input_artifacts: list[Artifact],
    ) -> list[Artifact]:
        findings = self._extract_findings(input_artifacts)
        raw = await self._client.complete_json(
            f"Create a research report from these validated findings:\n{json.dumps(findings)}",
            system=SYSTEM_PROMPT,
        )
        content = self._parse_report(raw)

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                type="research_report",
                content=content,
                lineage=Lineage(
                    produced_by=task_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

    def _extract_findings(self, artifacts: list[Artifact]) -> dict:
        for art in artifacts:
            if isinstance(art.content, dict) and "validated_findings" in art.content:
                return art.content
        all_content = [art.content for art in artifacts if art.content]
        return {"validated_findings": all_content}

    def _parse_report(self, raw: str) -> dict:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {
                    "title": parsed.get("title", "Research Report"),
                    "summary": parsed.get("summary", ""),
                    "sections": parsed.get("sections", []),
                    "sources": parsed.get("sources", []),
                }
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "title": "Research Report",
            "summary": raw.strip(),
            "sections": [],
            "sources": [],
        }
