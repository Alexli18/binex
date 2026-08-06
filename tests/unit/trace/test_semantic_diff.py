"""Tests for semantic diff analysis, cost estimation, and CLI gating (#71)."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from binex.trace.semantic_diff import (
    analyze_diff,
    analyze_pair,
    changed_pairs,
)
from binex.trace.semantic_judge import estimate_cost


def _diff_with(steps: list[dict]) -> dict:
    return {"steps": steps}


def test_changed_pairs_only_real_content_changes() -> None:
    diff = _diff_with([
        {"task_id": "a", "content_a": "x", "content_b": "y",
         "content_similarity": 0.5, "artifacts_changed": True},
        {"task_id": "b", "content_a": "same", "content_b": "same",
         "content_similarity": 1.0, "artifacts_changed": False},
        {"task_id": "c", "content_a": None, "content_b": None,
         "content_similarity": 1.0},
    ])
    pairs = changed_pairs(diff)
    assert [p[0] for p in pairs] == ["a"]


def test_changed_pairs_stringifies_non_str() -> None:
    diff = _diff_with([
        {"task_id": "a", "content_a": {"k": 1}, "content_b": {"k": 2},
         "content_similarity": 0.6, "artifacts_changed": True},
    ])
    pairs = changed_pairs(diff)
    assert pairs[0][1] == "{'k': 1}"
    assert pairs[0][2] == "{'k': 2}"


async def _judge_structure(a: str, b: str) -> dict:
    return {
        "structure": {"changed": True, "confidence": "high", "reason": "field added"},
        "facts": {"changed": False, "confidence": "high", "reason": ""},
        "tone_format": {"changed": False, "confidence": "low", "reason": ""},
    }


async def _judge_cosmetic(a: str, b: str) -> dict:
    return {
        "structure": {"changed": False, "confidence": "high", "reason": ""},
        "facts": {"changed": False, "confidence": "high", "reason": ""},
        "tone_format": {"changed": True, "confidence": "high", "reason": "reworded"},
    }


@pytest.mark.asyncio
async def test_meaningful_change() -> None:
    v = await analyze_pair("n", "a", "b", _judge_structure)
    assert v.meaningful is True
    assert "structure" in v.summary


@pytest.mark.asyncio
async def test_cosmetic_change_collapsed() -> None:
    v = await analyze_pair("n", "a", "b", _judge_cosmetic)
    assert v.meaningful is False
    assert "cosmetic" in v.summary


@pytest.mark.asyncio
async def test_judge_error_is_fail_safe() -> None:
    async def broken(a: str, b: str) -> dict:
        raise RuntimeError("boom")

    v = await analyze_pair("n", "a", "b", broken)
    assert v.error == "boom"
    assert "could not analyze" in v.summary


@pytest.mark.asyncio
async def test_missing_answer_assumed_changed() -> None:
    async def empty(a: str, b: str) -> dict:
        return {}

    v = await analyze_pair("n", "a", "b", empty)
    # No answer for meaningful questions → conservatively 'changed'.
    assert v.meaningful is True
    assert all(q.confidence == "low" for q in v.questions)


@pytest.mark.asyncio
async def test_invalid_confidence_normalized() -> None:
    async def weird(a: str, b: str) -> dict:
        return {"facts": {"changed": True, "confidence": "SUPER", "reason": "r"}}

    v = await analyze_pair("n", "a", "b", weird)
    facts = next(q for q in v.questions if q.key == "facts")
    assert facts.confidence == "low"


@pytest.mark.asyncio
async def test_analyze_diff_only_changed_nodes() -> None:
    diff = _diff_with([
        {"task_id": "a", "content_a": "x", "content_b": "y",
         "content_similarity": 0.5, "artifacts_changed": True},
        {"task_id": "b", "content_a": "z", "content_b": "z",
         "content_similarity": 1.0, "artifacts_changed": False},
    ])
    verdicts = await analyze_diff(diff, _judge_structure)
    assert set(verdicts.keys()) == {"a"}


def test_estimate_cost_scales_with_pairs() -> None:
    one = estimate_cost([("n", "a" * 400, "b" * 400)], "gpt-4o-mini")
    two = estimate_cost(
        [("n", "a" * 400, "b" * 400), ("m", "c" * 400, "d" * 400)], "gpt-4o-mini",
    )
    assert two.calls == 2
    assert two.prompt_tokens > one.prompt_tokens
    assert two.completion_tokens == 2 * one.completion_tokens


def test_estimate_cost_local_model_is_free() -> None:
    est = estimate_cost([("n", "a", "b")], "ollama/llama3")
    assert est.calls == 1
    assert est.cost == 0.0  # local models cost nothing


def test_estimate_cost_unknown_model_unpriced() -> None:
    est = estimate_cost([("n", "a", "b")], "totally-fake-model-xyz")
    assert est.cost is None  # unknown model → no price available


# --- CLI gating: opt-in, cost shown, declinable ----------------------------

def _full_diff() -> dict:
    """A diff dict complete enough for format_diff to render."""
    return {
        "run_a": "run_a", "run_b": "run_b",
        "workflow_a": "wf", "workflow_b": "wf",
        "status_a": "completed", "status_b": "completed",
        "summary": {"total_nodes": 1, "changed_nodes": 1, "unchanged_nodes": 0,
                    "latency_delta_ms": 0.0, "cost_delta": 0.0,
                    "content_similarity": 0.5},
        "steps": [{
            "task_id": "a", "content_a": "x", "content_b": "y",
            "content_similarity": 0.5, "artifacts_changed": True,
            "status_changed": False, "agent_changed": False,
            "status_a": "completed", "status_b": "completed",
            "agent_a": "x", "agent_b": "x",
            "latency_a": 10, "latency_b": 10,
        }],
    }


def test_diff_semantic_declined_makes_no_judge(monkeypatch) -> None:
    from binex.cli.diff import diff_cmd

    async def fake_run_diff(run_a: str, run_b: str) -> dict:
        return _full_diff()

    called = {"judge": False}

    def fake_make_judge(model: str, **kw):
        called["judge"] = True
        raise AssertionError("judge must not be built when declined")

    monkeypatch.setattr("binex.cli.diff._run_diff", fake_run_diff)
    monkeypatch.setattr("binex.trace.semantic_judge.make_semantic_judge", fake_make_judge)

    runner = CliRunner()
    # Answer "n" to the confirmation prompt.
    result = runner.invoke(
        diff_cmd, ["run_a", "run_b", "--semantic", "--no-rich"], input="n\n",
    )
    assert result.exit_code == 0
    assert called["judge"] is False
    # The estimate must be shown before the prompt.
    assert "estimated cost" in result.output.lower()


def test_diff_semantic_runs_when_confirmed(monkeypatch) -> None:
    from binex.cli.diff import diff_cmd

    async def fake_run_diff(run_a: str, run_b: str) -> dict:
        return _full_diff()

    monkeypatch.setattr("binex.cli.diff._run_diff", fake_run_diff)
    monkeypatch.setattr(
        "binex.trace.semantic_judge.make_semantic_judge",
        lambda model, **kw: _judge_structure,
    )

    runner = CliRunner()
    result = runner.invoke(
        diff_cmd, ["run_a", "run_b", "--semantic", "--yes", "--no-rich"],
    )
    assert result.exit_code == 0
    assert "Semantic analysis" in result.output
    assert "structure" in result.output
