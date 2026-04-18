"""Chain-of-Verification pattern: generate → extract_claims → verify_each → revise."""

from __future__ import annotations

from typing import Any

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "generate": "Generate initial response",
    "extract_claims": "Extract factual claims from the response",
    "verify_each": "Verify each claim for accuracy",
    "revise": "Revise the response correcting any inaccurate claims",
}

STEP_ORDER = ("generate", "extract_claims", "verify_each", "revise")


def expand_chain_of_verification(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict[str, Any]]]:
    """Expand chain-of-verification into generate → extract → verify → revise."""
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "chain_of_verification"}
    nodes: list[NodeSpec] = []

    for i, step_name in enumerate(STEP_ORDER):
        step_cfg = spec.steps.get(step_name)
        model = step_cfg.model if step_cfg and step_cfg.model else spec.model
        parts: list[str] = []
        if spec.system_prompt:
            parts.append(spec.system_prompt)
        step_prompt = (
            step_cfg.prompt if step_cfg and step_cfg.prompt else DEFAULT_PROMPTS[step_name]
        )
        parts.append(step_prompt)

        deps: list[str]
        if i == 0:
            deps = list(spec.depends_on)
        else:
            deps = [f"{spec.id}.{STEP_ORDER[i - 1]}"]

        nodes.append(NodeSpec(
            id=f"{spec.id}.{step_name}",
            agent=model,
            system_prompt="\n\n".join(parts),
            depends_on=deps,
            inputs=spec.inputs if i == 0 else {},
            outputs=spec.outputs if step_name == "revise" else ["result"],
            config={**group_meta},
            budget=spec.budget,
        ))

    edges: list[tuple[str, str]] = []
    for i in range(len(STEP_ORDER) - 1):
        edges.append((f"{spec.id}.{STEP_ORDER[i]}", f"{spec.id}.{STEP_ORDER[i + 1]}"))

    return nodes, edges, []
