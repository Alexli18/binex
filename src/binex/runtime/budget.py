"""Budget logic — policy resolution, cost limits, and batch budget checks."""

from __future__ import annotations

from binex.graph.scheduler import Scheduler
from binex.models.workflow import NodeSpec, WorkflowSpec


def get_effective_policy(spec: WorkflowSpec) -> str:
    """Return the effective budget policy — from workflow or default 'stop'."""
    if spec.budget:
        return spec.budget.policy
    return "stop"


def get_node_max_cost(
    node: NodeSpec, spec: WorkflowSpec, accumulated_workflow_cost: float
) -> float | None:
    """Return effective max_cost for a node, considering workflow budget."""
    if node.budget is None:
        return None
    node_max = node.budget.max_cost
    if spec.budget:
        remaining = spec.budget.max_cost - accumulated_workflow_cost
        return min(node_max, remaining)
    return node_max


def check_batch_budget(
    spec: WorkflowSpec, accumulated_cost: float,
) -> str | None:
    """Check budget before scheduling a batch.

    Returns "stop", "warn", or None (no budget issue).
    """
    if not spec.budget or spec.budget.max_cost <= 0:
        return None
    if accumulated_cost <= spec.budget.max_cost:
        return None
    return spec.budget.policy  # "stop" or "warn"


def skip_all_remaining(
    scheduler: Scheduler, initial_ready: list[str],
) -> None:
    """Skip all ready and subsequently unblocked nodes."""
    for node_id in initial_ready:
        scheduler.mark_skipped(node_id)
    while not scheduler.is_complete() and not scheduler.is_blocked():
        remaining = scheduler.ready_nodes()
        if not remaining:
            break
        for node_id in remaining:
            scheduler.mark_skipped(node_id)
