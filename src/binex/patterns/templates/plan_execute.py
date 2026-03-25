"""Plan-Execute pattern: planner → executor → verifier with back-edge."""

from __future__ import annotations

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "planner": "Create a step-by-step plan",
    "executor": "Execute the plan",
    "verifier": "Verify execution results. Output DONE if satisfactory.",
}

STEP_ORDER = ("planner", "executor", "verifier")


def expand_plan_execute(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict]]:
    """Expand plan-execute into planner → executor → verifier with back-edge."""
    max_iter = spec.config.get("max_iterations", 3)
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "plan_execute"}
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
            outputs=spec.outputs if step_name == "verifier" else ["result"],
            config={**group_meta},
            budget=spec.budget,
        ))

    edges: list[tuple[str, str]] = []
    for i in range(len(STEP_ORDER) - 1):
        edges.append((f"{spec.id}.{STEP_ORDER[i]}", f"{spec.id}.{STEP_ORDER[i + 1]}"))

    back_edges: list[dict] = [{
        "node_id": f"{spec.id}.verifier",
        "target": f"{spec.id}.planner",
        "max_iterations": max_iter,
        "when": "true",
    }]

    return nodes, edges, back_edges
