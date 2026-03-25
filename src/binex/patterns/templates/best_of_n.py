"""Best-of-N pattern template: parallel variants → judge."""

from __future__ import annotations

from typing import Any

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "variant": "Generate a solution",
    "judge": "Compare all variants and select the best one",
}


def expand_best_of_n(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict[str, Any]]]:
    """Expand best-of-N pattern into variant_1..N → judge."""
    n_variants = spec.config.get("variants", 3)
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "best_of_n"}
    nodes: list[NodeSpec] = []

    def _prompt(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        parts: list[str] = []
        if spec.system_prompt:
            parts.append(spec.system_prompt)
        default = DEFAULT_PROMPTS.get(step_name, DEFAULT_PROMPTS["variant"])
        step_prompt = (
            step_cfg.prompt if step_cfg and step_cfg.prompt else default
        )
        parts.append(step_prompt)
        return "\n\n".join(parts)

    def _model(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        return step_cfg.model if step_cfg and step_cfg.model else spec.model

    # Variant nodes (parallel)
    variant_ids: list[str] = []
    for i in range(1, n_variants + 1):
        step_name = f"variant_{i}"
        nid = f"{spec.id}.{step_name}"
        variant_ids.append(nid)
        nodes.append(NodeSpec(
            id=nid,
            agent=_model(step_name),
            system_prompt=_prompt(step_name),
            depends_on=list(spec.depends_on),
            inputs=spec.inputs if i == 1 else {},
            outputs=["result"],
            config={**group_meta},
            budget=spec.budget,
        ))

    # Judge
    nodes.append(NodeSpec(
        id=f"{spec.id}.judge",
        agent=_model("judge"),
        system_prompt=_prompt("judge"),
        depends_on=list(variant_ids),
        inputs={},
        outputs=spec.outputs if spec.outputs else ["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    # Edges
    edges: list[tuple[str, str]] = []
    for vid in variant_ids:
        edges.append((vid, f"{spec.id}.judge"))

    return nodes, edges, []
