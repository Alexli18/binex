"""Suite runner — executes all cases through the orchestrator non-interactively."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from binex.adapters.scripted_input import ScriptedInputAdapter
from binex.eval.compare import compare_case
from binex.eval.models import (
    EvalCase,
    EvalCaseResult,
    EvalResult,
    EvalSuite,
)
from binex.eval.suite_asserts import evaluate_asserts
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore
from binex.workflow_spec.loader import load_workflow


async def run_suite(
    suite: EvalSuite,
    *,
    parallel: int = 1,
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
) -> EvalResult:
    """Execute all cases in the suite and return an EvalResult."""
    sem = asyncio.Semaphore(max(1, parallel))

    async def _run_case(case: EvalCase) -> EvalCaseResult:
        async with sem:
            return await _execute_case(case, suite, exec_store, art_store)

    started_at = datetime.now(UTC)
    case_results = await asyncio.gather(*[_run_case(c) for c in suite.cases])

    total = len(case_results)
    passed = sum(1 for r in case_results if r.verdict == "pass")
    failed = sum(1 for r in case_results if r.verdict == "fail")
    no_baseline = sum(1 for r in case_results if r.verdict == "no_baseline")
    total_cost = sum(r.cost_delta or 0.0 for r in case_results if r.run_id)

    result = EvalResult(
        suite_name=suite.name,
        suite_path=suite.workflow,
        executed_at=started_at,
        total=total,
        passed=passed,
        failed=failed,
        no_baseline=no_baseline,
        total_cost=total_cost,
        cases=list(case_results),
    )

    await exec_store.save_eval_result(result)
    return result


async def _execute_case(
    case: EvalCase,
    suite: EvalSuite,
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
) -> EvalCaseResult:
    """Run a single eval case through the orchestrator and evaluate its results."""
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.runtime.orchestrator import Orchestrator

    try:
        spec = load_workflow(suite.workflow, user_vars=case.inputs)
    except Exception as exc:
        return EvalCaseResult(
            case_id=case.id,
            verdict="fail",
            error=f"Failed to load workflow: {exc}",
        )

    orch = Orchestrator(art_store, exec_store, interactive=False)

    # Register non-human adapters first
    register_workflow_adapters(
        orch.dispatcher,
        spec,
        workflow_dir=str(Path(suite.workflow).parent),
    )

    # Override human:// nodes with ScriptedInputAdapter
    scripted = ScriptedInputAdapter(case.inputs)
    for node in spec.nodes.values():
        if node.agent.startswith("human://"):
            orch.dispatcher.register_adapter(node.agent, scripted)

    try:
        summary = await orch.run_workflow(spec)
    except Exception as exc:
        return EvalCaseResult(
            case_id=case.id,
            verdict="fail",
            error=str(exc),
        )

    run_id = summary.run_id

    # Tag the run with eval metadata
    summary.eval_suite_id = suite.name
    summary.eval_case_id = case.id
    await exec_store.update_run(summary)

    # Look up baseline
    baselines = await exec_store.get_baselines(suite.name)
    baseline_run_id = baselines.get(case.id)

    # Compare against baseline
    case_result = await compare_case(
        case, run_id, baseline_run_id, suite.thresholds, exec_store, art_store
    )

    # Evaluate asserts
    assert_results = await evaluate_asserts(case, run_id, exec_store, art_store)
    any_assert_failed = any(r.status in ("failed", "error") for r in assert_results)

    # Merge assert results into case result
    final_verdict = case_result.verdict
    if any_assert_failed and final_verdict != "fail":
        final_verdict = "fail"

    return EvalCaseResult(
        case_id=case.id,
        verdict=final_verdict,
        run_id=run_id,
        baseline_run_id=baseline_run_id,
        similarity=case_result.similarity,
        cost_delta=case_result.cost_delta,
        latency_delta_ms=case_result.latency_delta_ms,
        violated_thresholds=case_result.violated_thresholds,
        assert_results=assert_results,
        error=case_result.error,
    )
