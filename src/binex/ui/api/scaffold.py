"""Scaffold API endpoints for Binex Web UI."""

from __future__ import annotations

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.cli.dsl_parser import PATTERNS, parse_dsl

router = APIRouter(prefix="/scaffold", tags=["scaffold"])


class ScaffoldRequest(BaseModel):
    """Request body for scaffolding a workflow."""

    mode: str  # "dsl" or "template"
    expression: str | None = None
    template_name: str | None = None


def _build_simple_workflow(nodes: list[str], depends_on: dict[str, list[str]]) -> dict:
    """Build a minimal workflow dict from parsed DSL."""
    node_specs: dict[str, dict] = {}
    for node_name in nodes:
        deps = depends_on.get(node_name, [])
        inputs: dict[str, str] = {}
        if deps:
            for dep in deps:
                inputs[dep] = f"${{{dep}.output}}"
        else:
            inputs["query"] = "${user.query}"

        spec: dict = {
            "agent": "local://echo",
            "system_prompt": "Process input",
            "inputs": inputs,
            "outputs": ["output"],
        }
        if deps:
            spec["depends_on"] = deps
        node_specs[node_name] = spec

    return {
        "name": "scaffold",
        "description": "Auto-generated workflow",
        "nodes": node_specs,
    }


@router.post("")
async def scaffold_workflow(body: ScaffoldRequest) -> JSONResponse:
    """Generate a workflow YAML from DSL or template."""
    if body.mode == "template":
        if not body.template_name:
            return JSONResponse(
                {"error": "template_name is required when mode is 'template'"},
                status_code=422,
            )
        if body.template_name not in PATTERNS:
            return JSONResponse(
                {"error": f"Unknown template '{body.template_name}'"},
                status_code=404,
            )
        dsl_string = PATTERNS[body.template_name]
    elif body.mode == "dsl":
        if not body.expression:
            return JSONResponse(
                {"error": "expression is required when mode is 'dsl'"},
                status_code=422,
            )
        dsl_string = body.expression
    else:
        return JSONResponse(
            {"error": f"Invalid mode '{body.mode}'. Use 'dsl' or 'template'."},
            status_code=422,
        )

    try:
        parsed = parse_dsl([dsl_string])
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=422)

    workflow = _build_simple_workflow(parsed.nodes, parsed.depends_on)
    yaml_str = yaml.dump(workflow, default_flow_style=False, sort_keys=False)

    return JSONResponse({
        "yaml": yaml_str,
        "nodes": parsed.nodes,
        "edges": [list(e) for e in parsed.edges],
    })


@router.get("/patterns")
async def list_patterns() -> JSONResponse:
    """List all available scaffold patterns."""
    patterns = [
        {
            "name": name,
            "description": dsl,
            "example": dsl,
        }
        for name, dsl in PATTERNS.items()
    ]
    return JSONResponse({"patterns": patterns})
