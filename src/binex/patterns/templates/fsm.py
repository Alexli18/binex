"""FSM pattern template: one node per state, linear chain with back-edges."""

from __future__ import annotations

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPT_TEMPLATE = "{state_name}: Process this state"


def expand_fsm(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict]]:
    """Expand FSM pattern into state nodes with linear edges and back-edges."""
    states: list[str] = spec.config.get("states", ["start", "end"])
    max_iter = spec.config.get("max_iterations", 3)
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "fsm"}
    nodes: list[NodeSpec] = []

    def _prompt(state_name: str) -> str:
        step_cfg = spec.steps.get(state_name)
        parts: list[str] = []
        if spec.system_prompt:
            parts.append(spec.system_prompt)
        step_prompt = (
            step_cfg.prompt if step_cfg and step_cfg.prompt
            else DEFAULT_PROMPT_TEMPLATE.format(state_name=state_name)
        )
        parts.append(step_prompt)
        return "\n\n".join(parts)

    def _model(state_name: str) -> str:
        step_cfg = spec.steps.get(state_name)
        return step_cfg.model if step_cfg and step_cfg.model else spec.model

    for i, state in enumerate(states):
        deps: list[str] = []
        if i == 0:
            deps = list(spec.depends_on)
        else:
            deps = [f"{spec.id}.{states[i - 1]}"]

        nodes.append(NodeSpec(
            id=f"{spec.id}.{state}",
            agent=_model(state),
            system_prompt=_prompt(state),
            depends_on=deps,
            inputs=spec.inputs if i == 0 else {},
            outputs=spec.outputs if i == len(states) - 1 else ["result"],
            config={**group_meta},
            budget=spec.budget,
        ))

    # Edges: linear chain
    edges: list[tuple[str, str]] = []
    for i in range(len(states) - 1):
        edges.append((f"{spec.id}.{states[i]}", f"{spec.id}.{states[i + 1]}"))

    # Back-edges: each state (except first) can go back to first state
    back_edges: list[dict] = []
    for state in states[1:]:
        back_edges.append({
            "node_id": f"{spec.id}.{state}",
            "target": f"{spec.id}.{states[0]}",
            "max_iterations": max_iter,
            "when": "true",
        })

    return nodes, edges, back_edges
