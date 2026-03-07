"""ValidatorAgent — deduplicates and validates research findings."""

from __future__ import annotations

import json
import uuid

from binex.agents.common.llm_client import LLMClient
from binex.models.artifact import Artifact, Lineage

SYSTEM_PROMPT = (
    "You are a research validator. Given multiple sets of research findings, "
    "deduplicate, verify consistency, and rate confidence. "
    "Return JSON with 'validated_findings' (array of strings), "
    "'duplicates_removed' (integer), and 'confidence_scores' "
    "(object mapping finding to a score between 0 and 1). No extra text."
)


class ValidatorAgent:
    """Reference agent that validates and deduplicates research results."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or LLMClient()

    async def execute(
        self,
        task_id: str,
        run_id: str,
        input_artifacts: list[Artifact],
    ) -> list[Artifact]:
        combined = self._combine_findings(input_artifacts)
        raw = await self._client.complete_json(
            f"Validate and deduplicate these research findings:\n{json.dumps(combined)}",
            system=SYSTEM_PROMPT,
        )
        content = self._parse_validation(raw)

        return [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=run_id,
                type="validated_results",
                content=content,
                lineage=Lineage(
                    produced_by=task_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

    def _combine_findings(self, artifacts: list[Artifact]) -> list[dict]:
        results = []
        for art in artifacts:
            if isinstance(art.content, dict) and "findings" in art.content:
                results.append(art.content)
            elif isinstance(art.content, str):
                results.append({"findings": [art.content], "sources": []})
        return results

    def _parse_validation(self, raw: str) -> dict:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {
                    "validated_findings": parsed.get("validated_findings", []),
                    "duplicates_removed": parsed.get("duplicates_removed", 0),
                    "confidence_scores": parsed.get("confidence_scores", {}),
                }
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "validated_findings": [raw.strip()],
            "duplicates_removed": 0,
            "confidence_scores": {},
        }
