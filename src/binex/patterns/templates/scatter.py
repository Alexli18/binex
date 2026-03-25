"""Scatter pattern template: mapper → worker_1..N (parallel) → reducer."""

from __future__ import annotations

from binex.models.workflow import NodeSpec
from binex.patterns.models import PatternSpec

DEFAULT_PROMPTS = {
    "mapper": "Split the input into sub-tasks",
    "worker": "Process the assigned sub-task",
    "reducer": "Combine all worker results",
}


def expand_scatter(
    spec: PatternSpec,
) -> tuple[list[NodeSpec], list[tuple[str, str]], list[dict]]:
    """Expand scatter pattern into mapper → workers → reducer."""
    n_workers = spec.config.get("max_workers", 10)
    group_meta = {"_pattern_group": spec.id, "_pattern_type": "scatter"}
    nodes: list[NodeSpec] = []

    def _prompt(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        parts: list[str] = []
        if spec.system_prompt:
            parts.append(spec.system_prompt)
        step_prompt = (
            step_cfg.prompt if step_cfg and step_cfg.prompt else DEFAULT_PROMPTS.get(step_name, DEFAULT_PROMPTS["worker"])
        )
        parts.append(step_prompt)
        return "\n\n".join(parts)

    def _model(step_name: str) -> str:
        step_cfg = spec.steps.get(step_name)
        return step_cfg.model if step_cfg and step_cfg.model else spec.model

    # Mapper
    nodes.append(NodeSpec(
        id=f"{spec.id}.mapper",
        agent=_model("mapper"),
        system_prompt=_prompt("mapper"),
        depends_on=list(spec.depends_on),
        inputs=spec.inputs,
        outputs=["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    # Workers (parallel)
    worker_ids: list[str] = []
    for i in range(1, n_workers + 1):
        step_name = f"worker_{i}"
        nid = f"{spec.id}.{step_name}"
        worker_ids.append(nid)
        nodes.append(NodeSpec(
            id=nid,
            agent=_model(step_name),
            system_prompt=_prompt(step_name),
            depends_on=[f"{spec.id}.mapper"],
            inputs={},
            outputs=["result"],
            config={**group_meta},
            budget=spec.budget,
        ))

    # Reducer
    nodes.append(NodeSpec(
        id=f"{spec.id}.reducer",
        agent=_model("reducer"),
        system_prompt=_prompt("reducer"),
        depends_on=list(worker_ids),
        inputs={},
        outputs=spec.outputs if spec.outputs else ["result"],
        config={**group_meta},
        budget=spec.budget,
    ))

    # Edges
    edges: list[tuple[str, str]] = []
    for wid in worker_ids:
        edges.append((f"{spec.id}.mapper", wid))
        edges.append((wid, f"{spec.id}.reducer"))

    return nodes, edges, []
