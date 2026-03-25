"""Reflexion pattern template: actor → reflector with back-edge."""

from __future__ import annotations

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "actor": "Attempt the task",
    "reflector": "Reflect on the attempt. Output DONE if satisfactory, or provide improvement guidance.",
}


def expand_reflexion(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict]]:
    """Expand reflexion pattern into actor → reflector with back-edge."""
    max_iter = spec.config.get("max_iterations", 3)
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "reflexion"}
    nodes: list[NodeSpec] = []

    def _prompt(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        parts: list[str] = []
        if spec.system_prompt:
            parts.append(spec.system_prompt)
        step_prompt = (
            step_cfg.prompt if step_cfg and step_cfg.prompt else DEFAULT_PROMPTS[step_name]
        )
        parts.append(step_prompt)
        return "\n\n".join(parts)

    def _model(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        return step_cfg.model if step_cfg and step_cfg.model else spec.model

    # Actor
    nodes.append(NodeSpec(
        id=f"{spec.id}.actor",
        agent=_model("actor"),
        system_prompt=_prompt("actor"),
        depends_on=list(spec.depends_on),
        inputs=spec.inputs,
        outputs=["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    # Reflector
    nodes.append(NodeSpec(
        id=f"{spec.id}.reflector",
        agent=_model("reflector"),
        system_prompt=_prompt("reflector"),
        depends_on=[f"{spec.id}.actor"],
        inputs={},
        outputs=spec.outputs if spec.outputs else ["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    edges: list[tuple[str, str]] = [
        (f"{spec.id}.actor", f"{spec.id}.reflector"),
    ]

    back_edges: list[dict] = [{
        "node_id": f"{spec.id}.reflector",
        "target": f"{spec.id}.actor",
        "max_iterations": max_iter,
        "when": "true",
    }]

    return nodes, edges, back_edges
