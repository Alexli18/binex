"""Scaffold API endpoints for Binex Web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from binex.cli.dsl_parser import PATTERN_METADATA, PATTERNS, parse_dsl
from binex.cli.scaffold import AGENTIC_PROMPTS

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _resolve_prompt(file_ref: str) -> str:
    """Resolve a file://prompts/... reference to its actual content."""
    if not file_ref.startswith("file://prompts/"):
        return file_ref
    filename = file_ref.removeprefix("file://prompts/")
    path = _PROMPTS_DIR / filename
    if path.is_file():
        return path.read_text().strip()
    return file_ref

router = APIRouter(prefix="/scaffold", tags=["scaffold"])


class ScaffoldRequest(BaseModel):
    """Request body for scaffolding a workflow."""

    mode: str  # "dsl" or "template"
    expression: str | None = None
    template_name: str | None = None


_ROLE_PROMPTS: dict[str, str] = {
    "researcher": (
        "Research the topic thoroughly. Gather relevant facts, "
        "data, and sources. Provide a comprehensive summary."
    ),
    "writer": (
        "Write clear, well-structured content based on the "
        "provided input. Focus on clarity and engagement."
    ),
    "editor": (
        "Review and edit the content for grammar, style, "
        "clarity, and consistency. Suggest improvements."
    ),
    "reviewer": (
        "Review the work critically. Identify issues, suggest "
        "improvements, and assess overall quality."
    ),
    "summarizer": (
        "Synthesize and summarize all inputs into a concise, "
        "coherent final output. Highlight key conclusions."
    ),
    "aggregator": (
        "Merge and deduplicate information from all sources. "
        "Produce a unified, comprehensive output."
    ),
    "classifier": (
        "Classify the input into the appropriate category. "
        "Explain your reasoning."
    ),
    "validator": (
        "Validate the input for correctness, completeness, "
        "and consistency. Report any issues found."
    ),
    "processor": (
        "Process the input according to the task requirements. "
        "Transform data as needed."
    ),
    "analyzer": (
        "Analyze the input data. Identify patterns, trends, "
        "and insights. Provide actionable recommendations."
    ),
    "drafter": (
        "Create an initial draft based on the requirements. "
        "Focus on structure and completeness."
    ),
    "fetcher": (
        "Retrieve and extract the requested information "
        "from the available sources."
    ),
    "reporter": (
        "Generate a structured report from the provided data. "
        "Include key metrics and findings."
    ),
    "router": (
        "Analyze the input and determine the best processing "
        "path. Route to the appropriate handler."
    ),
}


def _smart_prompt(node_name: str) -> str:
    """Generate a meaningful prompt based on node name."""
    clean = node_name.lower().replace("-", "_").rstrip("0123456789")
    # Exact match
    if clean in _ROLE_PROMPTS:
        return _ROLE_PROMPTS[clean]
    # Partial match
    for role, prompt in _ROLE_PROMPTS.items():
        if role in clean:
            return prompt
    # Fallback: derive from name
    label = node_name.replace("_", " ").replace("-", " ").title()
    return f"You are the {label} agent. Process the input and produce your output."


def _build_simple_workflow(nodes: list[str], depends_on: dict[str, list[str]]) -> dict[str, Any]:
    """Build a minimal workflow dict from parsed DSL."""
    node_specs: dict[str, dict[str, Any]] = {}
    for node_name in nodes:
        deps = depends_on.get(node_name, [])
        inputs: dict[str, str] = {}
        if deps:
            for dep in deps:
                inputs[dep] = f"${{{dep}.output}}"
        else:
            inputs["query"] = "${user.query}"

        # Detect human nodes (approve, confirm, feedback, etc.)
        lower_name = node_name.lower().replace("-", "_")
        _human_kw = {"approve", "confirm", "gate", "input", "feedback", "human", "review"}
        is_human = any(kw in lower_name for kw in _human_kw)

        if is_human:
            _approve_kw = {"approve", "confirm", "gate"}
            htype = "approve" if any(kw in lower_name for kw in _approve_kw) else "input"
            agent = f"human://{htype}"
            prompt = "Review and approve" if htype == "approve" else "Provide your input"
        elif node_name in AGENTIC_PROMPTS:
            agent = "llm://openai/gpt-4o-mini"
            prompt = _resolve_prompt(AGENTIC_PROMPTS[node_name])
        else:
            agent = "llm://openai/gpt-4o-mini"
            prompt = _smart_prompt(node_name)

        spec: dict[str, Any] = {
            "agent": agent,
            "system_prompt": prompt,
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
    """List all available scaffold patterns with rich metadata."""
    patterns = [
        {
            "name": name,
            "dsl": info.dsl,
            "description": info.description,
            "use_case": info.use_case,
            "category": info.category,
            "node_count": info.node_count,
            "tags": list(info.tags),
        }
        for name, info in PATTERN_METADATA.items()
    ]
    return JSONResponse({"patterns": patterns})
