"""FastAPI registry app with REST endpoints for agent management."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from binex.models.agent import AgentHealth, AgentInfo


class RegisterAgentRequest(BaseModel):
    """Request body for registering an agent."""

    id: str | None = None
    endpoint: str
    name: str
    capabilities: list[str] = Field(default_factory=list)
    agent_card: dict[str, Any] = Field(default_factory=dict)


class RegistryState:
    """In-memory store for registered agents."""

    def __init__(self) -> None:
        self.agents: dict[str, AgentInfo] = {}


registry_state = RegistryState()
app = FastAPI(title="Binex Agent Registry")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agents", status_code=201)
def register_agent(req: RegisterAgentRequest) -> AgentInfo:
    agent_id = req.id or uuid.uuid4().hex[:12]
    agent = AgentInfo(
        id=agent_id,
        endpoint=req.endpoint,
        name=req.name,
        capabilities=req.capabilities,
        agent_card=req.agent_card,
    )
    registry_state.agents[agent_id] = agent
    return agent


@app.get("/agents/search")
def search_agents(capability: str) -> list[AgentInfo]:
    return [
        a for a in registry_state.agents.values()
        if capability in a.capabilities
    ]


@app.get("/agents")
def list_agents(
    capability: str | None = None,
    health: AgentHealth | None = None,
) -> list[AgentInfo]:
    results = list(registry_state.agents.values())
    if capability is not None:
        results = [a for a in results if capability in a.capabilities]
    if health is not None:
        results = [a for a in results if a.health == health]
    return results


@app.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> AgentInfo:
    if agent_id not in registry_state.agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return registry_state.agents[agent_id]


@app.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str) -> Response:
    if agent_id not in registry_state.agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    del registry_state.agents[agent_id]
    return Response(status_code=204)
