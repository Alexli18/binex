"""Critic pattern template: draft -> critique -> refine expansion."""

from __future__ import annotations

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "draft": "Based on the input, produce a thorough draft.",
    "critique": "Review the draft. List specific weaknesses, gaps, and errors.",
    "refine": "Revise the draft addressing each critique point.",
}


def expand_critic(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict]]:
    """Expand critic pattern into draft -> critique -> refine nodes."""
    rounds = spec.config.get("rounds", 1)
    nodes: list[NodeSpec] = []
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "critic"}

    for step_name in ("draft", "critique", "refine"):
        step_cfg = spec.steps.get(step_name)
        model = step_cfg.model if step_cfg and step_cfg.model else spec.model
        prompt_parts: list[str] = []
        if spec.system_prompt:
            prompt_parts.append(spec.system_prompt)
        step_prompt = (
            step_cfg.prompt
            if step_cfg and step_cfg.prompt
            else DEFAULT_PROMPTS[step_name]
        )
        prompt_parts.append(step_prompt)

        node = NodeSpec(
            id=f"{spec.id}.{step_name}",
            agent=model,
            system_prompt="\n\n".join(prompt_parts),
            depends_on=[],
            inputs=spec.inputs if step_name == "draft" else {},
            outputs=spec.outputs if step_name == "refine" else ["result"],
            config={**group_meta},
            budget=spec.budget,
        )
        nodes.append(node)

    # Wire depends_on
    nodes[0].depends_on = list(spec.depends_on)  # draft inherits external deps
    nodes[1].depends_on = [f"{spec.id}.draft"]
    nodes[2].depends_on = [f"{spec.id}.critique"]

    # Edges
    edges: list[tuple[str, str]] = [
        (f"{spec.id}.draft", f"{spec.id}.critique"),
        (f"{spec.id}.critique", f"{spec.id}.refine"),
    ]

    # Back-edge for multiple rounds
    back_edges: list[dict] = []
    if rounds > 1:
        back_edges.append({
            "node_id": f"{spec.id}.refine",
            "target": f"{spec.id}.draft",
            "max_iterations": rounds,
            "when": "true",
        })

    return nodes, edges, back_edges
