"""Constitutional pattern template: generate → critique_principles → revise."""

from __future__ import annotations

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "generate": "Generate initial response",
    "critique_principles": "Evaluate against constitutional principles",
    "revise": "Revise to address principle violations",
}


def expand_constitutional(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict]]:
    """Expand constitutional pattern into generate → critique_principles → revise."""
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "constitutional"}
    nodes: list[NodeSpec] = []

    for i, step_name in enumerate(("generate", "critique_principles", "revise")):
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
        elif i == 1:
            deps = [f"{spec.id}.generate"]
        else:
            deps = [f"{spec.id}.critique_principles"]

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

    edges: list[tuple[str, str]] = [
        (f"{spec.id}.generate", f"{spec.id}.critique_principles"),
        (f"{spec.id}.critique_principles", f"{spec.id}.revise"),
    ]

    return nodes, edges, []
