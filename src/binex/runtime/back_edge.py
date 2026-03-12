"""Back-edge evaluation logic extracted from orchestrator."""

from __future__ import annotations

import re

import click

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact
from binex.models.workflow import WorkflowSpec

_WHEN_RE = re.compile(r"^\$\{([\w-]+)\.([\w-]+)\}\s*(==|!=)\s*(.+)$")


def evaluate_when(when_str: str, node_artifacts: dict[str, list[Artifact]]) -> bool:
    """Evaluate a when-condition string against collected node artifacts.

    Returns True if the condition is satisfied, False otherwise.
    Raises ValueError for malformed when strings.
    """
    m = _WHEN_RE.match(when_str.strip())
    if not m:
        raise ValueError(f"Invalid when condition syntax: {when_str!r}")

    node_id, output_name, operator, value = m.group(1), m.group(2), m.group(3), m.group(4).strip()

    artifacts = node_artifacts.get(node_id)
    if not artifacts:
        return False

    # Match artifact by type (output_name), fall back to first artifact
    matching = [a for a in artifacts if a.type == output_name]
    actual = str(matching[0].content) if matching else str(artifacts[0].content)

    if operator == "==":
        return actual == value
    else:  # !=
        return actual != value


async def evaluate_back_edge(
    spec: WorkflowSpec,
    scheduler: Scheduler,
    dag: DAG,
    node_id: str,
    node_artifacts: dict[str, list[Artifact]],
    node_artifacts_history: dict[str, list[list[Artifact]]],
    pending_feedback: dict[str, list[Artifact]],
) -> None:
    """Evaluate back_edge after successful node execution. Resets chain if triggered."""
    back_edge = spec.nodes[node_id].back_edge
    if back_edge is None:
        return

    if not evaluate_when(back_edge.when, node_artifacts):
        return

    iteration = scheduler.get_execution_count(node_id)
    if iteration >= back_edge.max_iterations:
        decision = click.prompt(
            f"  Max iterations ({back_edge.max_iterations}) reached for '{node_id}'. "
            f"[a]ccept last draft · [f]ail workflow",
            type=click.Choice(["a", "f"]),
            show_choices=False,
        )
        if decision == "f":
            scheduler.mark_failed(node_id)
        return

    # Collect feedback artifacts for injection into target node
    feedback_arts = [
        a for a in node_artifacts.get(node_id, [])
        if a.type == "feedback"
    ]
    if feedback_arts:
        pending_feedback[back_edge.target] = feedback_arts

    # Reset chain and archive old artifacts
    reset_nodes = scheduler.reset_chain(back_edge.target, node_id, dag)
    for nid in reset_nodes:
        old = node_artifacts.pop(nid, [])
        node_artifacts_history.setdefault(nid, []).append(old)
