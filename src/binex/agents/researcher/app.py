"""FastAPI app for the researcher reference agent."""

from __future__ import annotations

import uuid

from fastapi import FastAPI

from binex.agents.common.llm_client import LLMClient
from binex.agents.common.llm_config import LLMConfig
from binex.agents.researcher.agent import ResearcherAgent
from binex.models.artifact import Artifact, Lineage

app = FastAPI(title="Binex Researcher Agent")
_agent = ResearcherAgent(LLMClient(LLMConfig()))


@app.post("/execute")
async def execute(payload: dict) -> dict:
    task_id = payload.get("task_id", "unknown")
    run_id = payload.get("run_id", f"run_{uuid.uuid4().hex[:8]}")
    input_artifacts = [
        Artifact(
            id=a.get("id", f"art_{uuid.uuid4().hex[:8]}"),
            run_id=run_id,
            type=a.get("type", "input"),
            content=a.get("content"),
            lineage=Lineage(produced_by="external", derived_from=[]),
        )
        for a in payload.get("artifacts", [])
    ]

    results = await _agent.execute(task_id, run_id, input_artifacts)
    return {
        "artifacts": [
            {"id": r.id, "type": r.type, "content": r.content}
            for r in results
        ]
    }


@app.post("/cancel")
async def cancel(payload: dict) -> dict:
    return {"status": "acknowledged"}


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "agent": "researcher"}
