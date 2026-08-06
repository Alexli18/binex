"""Unit tests for the eval runner's divergence logic (issue #60)."""

from __future__ import annotations

from binex.eval.golden import EvalReport, EvalThresholds, check_divergences


def _diff(similarity: float = 1.0, latency: float = 0.0, cost: float = 0.0,
          status_change: bool = False) -> dict:
    return {
        "summary": {
            "content_similarity": similarity,
            "latency_delta_ms": latency,
            "cost_delta": cost,
        },
        "steps": [
            {
                "task_id": "n1",
                "status_changed": status_change,
                "status_a": "completed",
                "status_b": "failed" if status_change else "completed",
            }
        ],
    }


def test_identical_run_no_divergence() -> None:
    assert check_divergences(_diff(), EvalThresholds()) == []


def test_similarity_below_threshold_diverges() -> None:
    out = check_divergences(_diff(similarity=0.8), EvalThresholds(min_similarity=1.0))
    assert out and "similarity" in out[0]


def test_similarity_within_loosened_threshold() -> None:
    out = check_divergences(_diff(similarity=0.95), EvalThresholds(min_similarity=0.9))
    assert out == []


def test_latency_delta_gate() -> None:
    th = EvalThresholds(max_latency_delta_ms=100)
    assert check_divergences(_diff(latency=50), th) == []
    assert check_divergences(_diff(latency=500), th)


def test_cost_delta_gate() -> None:
    th = EvalThresholds(max_cost_delta=0.01)
    assert check_divergences(_diff(cost=0.005), th) == []
    assert check_divergences(_diff(cost=0.1), th)


def test_status_change_always_diverges() -> None:
    out = check_divergences(_diff(status_change=True), EvalThresholds())
    assert any("status" in d for d in out)


def test_report_passed_property() -> None:
    assert EvalReport(run_id="r", run_status="completed").passed is True
    assert EvalReport(run_id="r", run_status="failed").passed is False
    assert EvalReport(
        run_id="r", run_status="completed", divergences=["x"],
    ).passed is False
