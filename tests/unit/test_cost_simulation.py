"""Tests for cost simulation — src/binex/cost_simulation.py."""

from __future__ import annotations

import pytest

from binex.cost_simulation import (
    DOWNSTREAM_BAND,
    TOKENIZER_BAND,
    price_tokens,
    simulate,
)
from binex.models.cost import CostRecord


def _rec(task_id: str, model: str, pt: int, ct: int, cost: float) -> CostRecord:
    return CostRecord(
        id=f"c_{task_id}", run_id="run1", task_id=task_id, cost=cost,
        source="llm_tokens", model=model, prompt_tokens=pt, completion_tokens=ct,
    )


def test_price_tokens_known_model():
    cost = price_tokens("gpt-4o", 1000, 500)
    assert cost is not None and cost > 0


def test_price_tokens_unknown_model_returns_none():
    assert price_tokens("totally-made-up-model-xyz", 1000, 500) is None


def test_swap_single_node_reprices_with_band():
    records = [
        _rec("a", "gpt-4o", 1000, 500, 0.0075),
        _rec("b", "gpt-4o", 2000, 200, 0.007),
    ]
    result = simulate(
        records, target_model="gpt-4o-mini",
        swapped_nodes={"a"}, downstream_nodes=set(),
    )
    by = {n.node_id: n for n in result.nodes}

    # 'a' repriced on the cheaper model, with a ±10% band around the estimate.
    a = by["a"]
    assert a.affected == "swapped"
    assert a.model_to == "gpt-4o-mini"
    assert a.est_low < a.est_high
    mid = (a.est_low + a.est_high) / 2
    assert a.est_low == pytest.approx(mid * (1 - TOKENIZER_BAND))
    assert a.est_high == pytest.approx(mid * (1 + TOKENIZER_BAND))
    assert a.est_high < a.orig_cost  # mini is cheaper than gpt-4o

    # 'b' untouched.
    assert by["b"].affected == "unchanged"
    assert by["b"].est_low == by["b"].est_high == pytest.approx(0.007)


def test_downstream_nodes_get_widened_band():
    records = [
        _rec("a", "gpt-4o", 1000, 500, 0.0075),
        _rec("b", "gpt-4o", 2000, 200, 0.010),
    ]
    result = simulate(
        records, target_model="gpt-4o-mini",
        swapped_nodes={"a"}, downstream_nodes={"b"},
    )
    b = next(n for n in result.nodes if n.node_id == "b")
    assert b.affected == "downstream"
    assert b.est_low == pytest.approx(0.010 * (1 - DOWNSTREAM_BAND))
    assert b.est_high == pytest.approx(0.010 * (1 + DOWNSTREAM_BAND))


def test_all_nodes_swap():
    records = [
        _rec("a", "gpt-4o", 1000, 500, 0.0075),
        _rec("b", "gpt-4o", 2000, 200, 0.010),
    ]
    result = simulate(
        records, target_model="gpt-4o-mini",
        swapped_nodes={"a", "b"}, downstream_nodes=set(),
    )
    assert all(n.affected == "swapped" for n in result.nodes)
    # Total range brackets a cheaper estimate than the original.
    assert result.est_high_total < result.orig_total
    assert result.est_low_total < result.est_high_total


def test_unpriced_target_keeps_original_and_flags():
    records = [_rec("a", "gpt-4o", 1000, 500, 0.0075)]
    result = simulate(
        records, target_model="made-up-model",
        swapped_nodes={"a"}, downstream_nodes=set(),
    )
    a = result.nodes[0]
    assert a.priced is False
    assert a.est_low == a.est_high == pytest.approx(0.0075)


def test_multiple_records_per_node_aggregate():
    records = [
        _rec("a", "gpt-4o", 500, 250, 0.004),
        _rec("a", "gpt-4o", 500, 250, 0.004),  # retry
    ]
    result = simulate(
        records, target_model="gpt-4o", swapped_nodes={"a"}, downstream_nodes=set(),
    )
    # Aggregated 1000/500 tokens; repriced on the same model ≈ original 0.0075.
    a = result.nodes[0]
    assert a.orig_cost == pytest.approx(0.008)
    mid = (a.est_low + a.est_high) / 2
    assert mid == pytest.approx(0.0075, rel=0.05)
