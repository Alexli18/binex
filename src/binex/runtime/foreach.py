"""Dynamic fan-out — runtime `foreach` expansion (#77).

A `foreach` node is a placeholder: when its mapper produces an array, the node
expands at runtime into one worker per item plus an aggregator, using DAG/
scheduler mutation (see :meth:`binex.graph.dag.DAG.add_node`). The scheduler
stays static in shape — "more nodes appeared".

This module holds the pure, side-effect-free pieces (parsing, identity, spec
building, guardrails, aggregation); the orchestrator wires them into the run
loop. v1 is deliberately non-nested and non-streaming (see the issue).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from binex.models.artifact import Artifact, Lineage
from binex.models.workflow import NodeSpec

AGGREGATOR_AGENT = "internal://foreach-aggregator"


class ForeachError(Exception):
    """A foreach node cannot be expanded (bad mapper output, too many items, budget)."""


@dataclass
class ForeachGroup:
    """Runtime bookkeeping for one expanded foreach node."""

    foreach_id: str
    mapper_id: str
    aggregator_id: str
    worker_ids: list[str]
    on_item_failure: str
    outputs: list[str]
    failed: list[str] = field(default_factory=list)

    def is_worker(self, node_id: str) -> bool:
        return node_id in self.worker_ids


def parse_items(content: Any) -> list[Any]:
    """Coerce a mapper's output into a list of items.

    Accepts a Python list, or a JSON string encoding a list. Anything else is a
    ForeachError — a foreach mapper must emit an array.
    """
    if isinstance(content, list):
        return content
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ForeachError(
                f"mapper output is not valid JSON: {exc}"
            ) from exc
        if isinstance(parsed, list):
            return parsed
        raise ForeachError("mapper output JSON is not an array")
    raise ForeachError(
        f"mapper output must be an array, got {type(content).__name__}"
    )


def _json_path_get(item: Any, path: str) -> Any:
    """Minimal JSONPath: only ``$.field`` / ``$.a.b`` dotted access."""
    if not path.startswith("$."):
        return None
    cur = item
    for part in path[2:].split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def item_identity(item: Any, item_key: str | None, index: int) -> str:
    """Stable identity for a fan-out item — a content hash or an explicit key.

    Keying by content (not index) means cache (#68) and cross-run diff still
    match "episode 42" even if it moved in the list.
    """
    if item_key:
        val = _json_path_get(item, item_key)
        if val is not None:
            return _slug(str(val))
    try:
        payload = json.dumps(item, sort_keys=True, default=str)
    except (TypeError, ValueError):
        payload = repr(item)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def _slug(text: str) -> str:
    """A filesystem/id-safe slug of an explicit key."""
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in text)
    return safe[:40] or "item"


def worker_node_id(foreach_id: str, ident: str) -> str:
    return f"{foreach_id}::{ident}"


def aggregator_node_id(foreach_id: str) -> str:
    return f"{foreach_id}::aggregate"


def build_worker_spec(foreach_node: NodeSpec, worker_id: str) -> NodeSpec:
    """Clone the foreach node into a single-item worker (no foreach/deps)."""
    return NodeSpec(
        id=worker_id,
        agent=foreach_node.agent,
        system_prompt=foreach_node.system_prompt,
        inputs=dict(foreach_node.inputs),
        outputs=list(foreach_node.outputs),
        depends_on=[],  # the item is injected as an input artifact
        config=dict(foreach_node.config),
        retry_policy=foreach_node.retry_policy,
        deadline_ms=foreach_node.deadline_ms,
        heartbeat_timeout_ms=foreach_node.heartbeat_timeout_ms,
        tools=list(foreach_node.tools),
        output_schema=foreach_node.output_schema,
        cache=foreach_node.cache,
        repair=foreach_node.repair,
        fallbacks=list(foreach_node.fallbacks),
        assertions=list(foreach_node.assertions),
    )


def build_aggregator_spec(
    foreach_node: NodeSpec, aggregator_id: str, worker_ids: list[str],
) -> NodeSpec:
    """The aggregator node — handled directly by the orchestrator, not an agent."""
    return NodeSpec(
        id=aggregator_id,
        agent=AGGREGATOR_AGENT,
        outputs=list(foreach_node.outputs) or ["results"],
        depends_on=list(worker_ids),
    )


def estimate_expansion_cost(
    foreach_node: NodeSpec, n_items: int,
) -> float | None:
    """Rough pre-flight cost of the workers, or None if not estimable.

    Uses the node's per-item budget hint (``budget.max_cost``) as the per-worker
    estimate — the only honest number we have before running anything.
    """
    from binex.models.cost import NodeBudget

    budget = foreach_node.budget
    if isinstance(budget, NodeBudget) and budget.max_cost is not None:
        return float(budget.max_cost) * n_items
    if isinstance(budget, (int, float)):
        return float(budget) * n_items
    return None


def build_aggregate_content(
    group: ForeachGroup,
    worker_outputs: dict[str, list[Artifact]],
) -> dict[str, Any]:
    """Assemble the aggregator's result: successes + a failure list."""
    results: list[Any] = []
    for wid in group.worker_ids:
        if wid in group.failed:
            continue
        arts = worker_outputs.get(wid, [])
        if arts:
            results.append(arts[0].content)
    return {
        "results": results,
        "total": len(group.worker_ids),
        "succeeded": len(group.worker_ids) - len(group.failed),
        "failed": list(group.failed),
    }


def make_item_artifact(run_id: str, worker_id: str, item: Any) -> Artifact:
    """The per-worker input artifact carrying its single item."""
    return Artifact(
        id=f"art_item_{hashlib.sha256(worker_id.encode()).hexdigest()[:12]}",
        run_id=run_id,
        type="foreach_item",
        content=item,
        lineage=Lineage(produced_by=worker_id),
    )


__all__ = [
    "AGGREGATOR_AGENT",
    "ForeachError",
    "ForeachGroup",
    "aggregator_node_id",
    "build_aggregate_content",
    "build_aggregator_spec",
    "build_worker_spec",
    "estimate_expansion_cost",
    "item_identity",
    "make_item_artifact",
    "parse_items",
    "worker_node_id",
]
