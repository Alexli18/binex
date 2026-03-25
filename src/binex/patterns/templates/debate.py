"""Debate pattern template: parallel agents → collector → judge."""

from __future__ import annotations

from typing import Any

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "agent": "Argue your position on the topic",
    "collector": "Collect all arguments",
    "judge": "Evaluate arguments and render a verdict",
}


def expand_debate(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict[str, Any]]]:
    """Expand debate pattern into agent_1..N → collector → judge."""
    n_agents = spec.config.get("agents", 2)
    rounds = spec.config.get("rounds", 1)
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "debate"}
    nodes: list[NodeSpec] = []

    def _prompt(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        parts: list[str] = []
        if spec.system_prompt:
            parts.append(spec.system_prompt)
        default = DEFAULT_PROMPTS.get(step_name, DEFAULT_PROMPTS["agent"])
        step_prompt = (
            step_cfg.prompt if step_cfg and step_cfg.prompt else default
        )
        parts.append(step_prompt)
        return "\n\n".join(parts)

    def _model(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        return step_cfg.model if step_cfg and step_cfg.model else spec.model

    # Agent nodes (parallel)
    agent_ids: list[str] = []
    for i in range(1, n_agents + 1):
        step_name = f"agent_{i}"
        nid = f"{spec.id}.{step_name}"
        agent_ids.append(nid)
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

    # Collector
    nodes.append(NodeSpec(
        id=f"{spec.id}.collector",
        agent=_model("collector"),
        system_prompt=_prompt("collector"),
        depends_on=list(agent_ids),
        inputs={},
        outputs=["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    # Judge
    nodes.append(NodeSpec(
        id=f"{spec.id}.judge",
        agent=_model("judge"),
        system_prompt=_prompt("judge"),
        depends_on=[f"{spec.id}.collector"],
        inputs={},
        outputs=spec.outputs if spec.outputs else ["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    # Edges
    edges: list[tuple[str, str]] = []
    for aid in agent_ids:
        edges.append((aid, f"{spec.id}.collector"))
    edges.append((f"{spec.id}.collector", f"{spec.id}.judge"))

    # Back-edge for multiple rounds
    back_edges: list[dict[str, Any]] = []
    if rounds > 1:
        back_edges.append({
            "node_id": f"{spec.id}.judge",
            "target": agent_ids[0],
            "max_iterations": rounds,
            "when": "true",
        })

    return nodes, edges, back_edges
