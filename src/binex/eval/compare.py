"""Baseline comparison — compare a case run against its blessed baseline."""

from __future__ import annotations

from binex.eval.models import EvalCase, EvalCaseResult, EvalThresholds
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore
from binex.trace.diff import diff_runs


async def compare_case(
    case: EvalCase,
    run_id: str,
    baseline_run_id: str | None,
    suite_thresholds: EvalThresholds,
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
) -> EvalCaseResult:
    """Compare the case run against its baseline using diff_runs.

    Returns an EvalCaseResult with verdict and threshold violation details.
    """
    if baseline_run_id is None:
        return EvalCaseResult(
            case_id=case.id,
            verdict="no_baseline",
            run_id=run_id,
            baseline_run_id=None,
        )

    # Merge thresholds: case-level wins field-by-field over suite-level
    thresholds = _merge_thresholds(suite_thresholds, case.thresholds)

    # Run comparison via existing diff engine
    try:
        diff = await diff_runs(exec_store, art_store, baseline_run_id, run_id)
    except ValueError as exc:
        return EvalCaseResult(
            case_id=case.id,
            verdict="fail",
            run_id=run_id,
            baseline_run_id=baseline_run_id,
            error=str(exc),
        )

    summary = diff.get("summary", {})
    similarity = summary.get("content_similarity")
    cost_delta_raw = summary.get("cost_delta")
    latency_delta_ms_raw = summary.get("latency_delta_ms")

    cost_delta = abs(cost_delta_raw) if cost_delta_raw is not None else None
    latency_delta_ms = (
        int(abs(latency_delta_ms_raw)) if latency_delta_ms_raw is not None else None
    )

    # Also compute cost delta from run total_cost fields for robustness
    run_obj = await exec_store.get_run(run_id)
    baseline_obj = await exec_store.get_run(baseline_run_id)
    if run_obj is not None and baseline_obj is not None:
        cost_delta = abs(run_obj.total_cost - baseline_obj.total_cost)

    violated: list[str] = []

    if thresholds.min_similarity is not None and similarity is not None:
        if similarity < thresholds.min_similarity:
            violated.append(
                f"min_similarity: {similarity:.4f} < {thresholds.min_similarity}"
            )

    if thresholds.max_cost_delta is not None and cost_delta is not None:
        if cost_delta > thresholds.max_cost_delta:
            violated.append(
                f"max_cost_delta: {cost_delta:.6f} > {thresholds.max_cost_delta}"
            )

    if thresholds.max_latency_delta_ms is not None and latency_delta_ms is not None:
        if latency_delta_ms > thresholds.max_latency_delta_ms:
            violated.append(
                f"max_latency_delta_ms: {latency_delta_ms} > {thresholds.max_latency_delta_ms}"
            )

    verdict = "fail" if violated else "pass"

    return EvalCaseResult(
        case_id=case.id,
        verdict=verdict,
        run_id=run_id,
        baseline_run_id=baseline_run_id,
        similarity=similarity,
        cost_delta=cost_delta,
        latency_delta_ms=latency_delta_ms,
        violated_thresholds=violated,
    )


def _merge_thresholds(
    suite: EvalThresholds, case: EvalThresholds | None
) -> EvalThresholds:
    """Merge suite and case thresholds — case value wins when not None."""
    if case is None:
        return suite
    return EvalThresholds(
        min_similarity=(
            case.min_similarity if case.min_similarity is not None else suite.min_similarity
        ),
        max_cost_delta=(
            case.max_cost_delta if case.max_cost_delta is not None else suite.max_cost_delta
        ),
        max_latency_delta_ms=(
            case.max_latency_delta_ms
            if case.max_latency_delta_ms is not None
            else suite.max_latency_delta_ms
        ),
    )
