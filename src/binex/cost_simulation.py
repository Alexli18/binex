"""Cost simulation — estimate what a run would have cost on a different model.

Uses the token counts already stored for a historical run plus litellm's pricing
table, so it makes **zero** LLM calls. Because a different model may answer at a
different length — and in a chain that output feeds the next node's input — the
estimate is presented as a **range**, widened for nodes downstream of a swap,
and always labelled as an estimate. See issue #70.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import litellm

from binex.models.cost import CostRecord

# Tokenizers differ between models, shifting counts by roughly ±10%.
TOKENIZER_BAND = 0.10
# A swapped node may change its output length, cascading into the input tokens
# of everything downstream — so widen those estimates substantially.
DOWNSTREAM_BAND = 0.40

DISCLAIMER = (
    "Estimated from historical token usage; not a quote. "
    "Ranges widen downstream of a swap."
)


def price_tokens(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Cost of the given token counts on ``model``, or None if the model is unpriced."""
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return float(prompt_cost + completion_cost)
    except Exception:
        return None


@dataclass
class NodeEstimate:
    node_id: str
    orig_cost: float
    est_low: float
    est_high: float
    model_from: str | None
    model_to: str | None
    affected: str  # "swapped" | "downstream" | "unchanged"
    priced: bool = True


@dataclass
class SimulationResult:
    target_model: str
    orig_total: float
    est_low_total: float
    est_high_total: float
    nodes: list[NodeEstimate] = field(default_factory=list)
    disclaimer: str = DISCLAIMER


@dataclass
class _NodeAgg:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    orig_cost: float = 0.0
    model: str | None = None
    has_tokens: bool = False


def _aggregate_by_node(cost_records: list[CostRecord]) -> dict[str, _NodeAgg]:
    """Sum token counts and cost per node (a node may have several records)."""
    by_node: dict[str, _NodeAgg] = {}
    for rec in cost_records:
        agg = by_node.setdefault(rec.task_id, _NodeAgg())
        agg.orig_cost += rec.cost
        agg.model = rec.model or agg.model
        if rec.prompt_tokens is not None or rec.completion_tokens is not None:
            agg.prompt_tokens += rec.prompt_tokens or 0
            agg.completion_tokens += rec.completion_tokens or 0
            agg.has_tokens = True
    return by_node


def simulate(
    cost_records: list[CostRecord],
    *,
    target_model: str,
    swapped_nodes: set[str],
    downstream_nodes: set[str],
) -> SimulationResult:
    """Estimate run cost after swapping ``swapped_nodes`` to ``target_model``.

    ``downstream_nodes`` (descendants of a swap) keep their recorded cost but get
    a wider uncertainty band, since their input tokens depend on the swapped
    node's output length. All other nodes are unchanged.
    """
    by_node = _aggregate_by_node(cost_records)
    nodes: list[NodeEstimate] = []
    orig_total = est_low_total = est_high_total = 0.0

    for node_id in sorted(by_node):
        agg = by_node[node_id]
        orig_total += agg.orig_cost

        if node_id in swapped_nodes:
            new_cost = (
                price_tokens(target_model, agg.prompt_tokens, agg.completion_tokens)
                if agg.has_tokens else None
            )
            if new_cost is None:
                # Unpriced model or no token data: keep original, flag it.
                est = NodeEstimate(
                    node_id, agg.orig_cost, agg.orig_cost, agg.orig_cost,
                    agg.model, target_model, "swapped", priced=False,
                )
            else:
                est = NodeEstimate(
                    node_id, agg.orig_cost,
                    new_cost * (1 - TOKENIZER_BAND), new_cost * (1 + TOKENIZER_BAND),
                    agg.model, target_model, "swapped",
                )
        elif node_id in downstream_nodes:
            est = NodeEstimate(
                node_id, agg.orig_cost,
                agg.orig_cost * (1 - DOWNSTREAM_BAND),
                agg.orig_cost * (1 + DOWNSTREAM_BAND),
                agg.model, agg.model, "downstream",
            )
        else:
            est = NodeEstimate(
                node_id, agg.orig_cost, agg.orig_cost, agg.orig_cost,
                agg.model, agg.model, "unchanged",
            )

        est_low_total += est.est_low
        est_high_total += est.est_high
        nodes.append(est)

    return SimulationResult(
        target_model=target_model,
        orig_total=orig_total,
        est_low_total=est_low_total,
        est_high_total=est_high_total,
        nodes=nodes,
    )
