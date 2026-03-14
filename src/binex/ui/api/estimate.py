"""Cost estimation API endpoint for Binex Web UI."""

from __future__ import annotations

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/costs", tags=["estimate"])


# Pricing per 1M tokens (USD)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
}

_DEFAULT_MAX_TOKENS = 4096


class EstimateRequest(BaseModel):
    """Request body for cost estimation."""

    yaml_content: str


def _extract_model_from_agent(agent: str) -> str | None:
    """Extract model name from an agent URI like 'llm://gpt-4o'."""
    if "://" in agent:
        return agent.split("://", 1)[1]
    return None


def _estimate_node(node_id: str, node_data: dict) -> dict:
    """Estimate cost for a single workflow node."""
    agent = node_data.get("agent", "")
    prefix = agent.split("://")[0] if "://" in agent else agent
    model = _extract_model_from_agent(agent)
    config = node_data.get("config", {}) or {}
    max_tokens = config.get("max_tokens", _DEFAULT_MAX_TOKENS)

    result: dict = {
        "node_id": node_id,
        "agent": agent,
        "model": model,
        "max_tokens": max_tokens,
        "estimated_cost": None,
        "type": prefix,
    }
    warnings: list[str] = []

    if prefix in ("local", "human"):
        result["estimated_cost"] = 0.0
    elif prefix == "a2a":
        result["estimated_cost"] = None
        warnings.append(f"{node_id}: a2a agent cost is unknown")
    elif prefix == "llm" and model:
        pricing = MODEL_PRICING.get(model)
        if pricing:
            # Worst case: max_tokens output
            cost_per_token = pricing["output"] / 1_000_000
            estimated = max_tokens * cost_per_token
            result["estimated_cost"] = round(estimated, 6)
            if max_tokens >= 4000:
                warnings.append(f"{node_id}: max_tokens={max_tokens} may be expensive")
        else:
            result["estimated_cost"] = None
            warnings.append(f"{node_id}: unknown model '{model}', cannot estimate cost")
    else:
        result["estimated_cost"] = None
        if model:
            warnings.append(f"{node_id}: unknown model '{model}', cannot estimate cost")

    return {**result, "warnings": warnings}


@router.post("/estimate")
async def cost_estimate(body: EstimateRequest) -> JSONResponse:
    """Estimate cost for a workflow defined in YAML."""
    try:
        data = yaml.safe_load(body.yaml_content)
    except yaml.YAMLError as exc:
        return JSONResponse(
            {"error": f"Invalid YAML: {exc}"},
            status_code=422,
        )

    if not isinstance(data, dict):
        return JSONResponse(
            {"error": "YAML must be a mapping"},
            status_code=422,
        )

    nodes_data = data.get("nodes", {})
    if not nodes_data:
        return JSONResponse({
            "total_estimate": 0.0,
            "nodes": [],
            "warnings": ["No nodes found in workflow"],
        })

    nodes = []
    all_warnings: list[str] = []
    total_estimate = 0.0
    has_unknown = False

    for node_id, node_data in nodes_data.items():
        if not isinstance(node_data, dict):
            continue
        result = _estimate_node(node_id, node_data)
        node_warnings = result.pop("warnings", [])
        all_warnings.extend(node_warnings)
        nodes.append(result)
        if result["estimated_cost"] is not None:
            total_estimate += result["estimated_cost"]
        else:
            has_unknown = True

    return JSONResponse({
        "total_estimate": round(total_estimate, 6),
        "nodes": nodes,
        "warnings": all_warnings,
    })
