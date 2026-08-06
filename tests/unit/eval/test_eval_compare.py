"""Tests for src/binex/eval/compare.py (T011, T017)."""

from __future__ import annotations

import pytest

from binex.eval.compare import compare_case
from binex.eval.models import EvalCase, EvalCaseResult, EvalThresholds
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(run_id: str, **kw) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test",
        status="completed",
        total_nodes=1,
        total_cost=kw.get("cost", 0.0),
        **{k: v for k, v in kw.items() if k != "cost"},
    )


def _record(run_id: str, node_id: str = "worker", latency_ms: int = 100) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"rec_{run_id}_{node_id}",
        run_id=run_id,
        task_id=node_id,
        agent_id="local://echo",
        status=TaskStatus.COMPLETED,
        output_artifact_refs=[f"art_{run_id}_{node_id}"],
        latency_ms=latency_ms,
        trace_id="trace",
    )


def _artifact(run_id: str, content: str, node_id: str = "worker") -> Artifact:
    return Artifact(
        id=f"art_{run_id}_{node_id}",
        run_id=run_id,
        type="output",
        content=content,
        lineage=Lineage(produced_by=node_id),
    )


async def _populate(
    es: InMemoryExecutionStore,
    ats: InMemoryArtifactStore,
    run_id: str,
    content: str,
    latency_ms: int = 100,
    cost: float = 0.01,
) -> None:
    run = _run(run_id, cost=cost)
    await es.create_run(run)
    await es.record(_record(run_id, latency_ms=latency_ms))
    await ats.store(_artifact(run_id, content))


# ---------------------------------------------------------------------------
# no_baseline — no entry in store
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_baseline_verdict_when_no_entry():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "run_a", "hello world")
    case = EvalCase(id="c1")
    result = await compare_case(
        case, "run_a", None, EvalThresholds(), es, ats
    )
    assert isinstance(result, EvalCaseResult)
    assert result.verdict == "no_baseline"
    assert result.run_id == "run_a"
    assert result.baseline_run_id is None


# ---------------------------------------------------------------------------
# pass — baseline present, thresholds not violated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pass_verdict_identical_content():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "baseline_run", "hello world")
    await _populate(es, ats, "current_run", "hello world")
    case = EvalCase(id="c1", thresholds=EvalThresholds(min_similarity=0.80))
    result = await compare_case(case, "current_run", "baseline_run", EvalThresholds(), es, ats)
    assert result.verdict == "pass"
    assert result.similarity is not None
    assert result.similarity >= 0.80


# ---------------------------------------------------------------------------
# fail — min_similarity threshold violated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_verdict_when_similarity_below_threshold():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "baseline_run", "The capital of France is Paris")
    await _populate(es, ats, "current_run", "banana mango pineapple tropical")
    case = EvalCase(id="c1", thresholds=EvalThresholds(min_similarity=0.90))
    result = await compare_case(case, "current_run", "baseline_run", EvalThresholds(), es, ats)
    assert result.verdict == "fail"
    assert any("min_similarity" in v for v in result.violated_thresholds)


# ---------------------------------------------------------------------------
# fail — max_cost_delta violated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_verdict_when_cost_delta_exceeded():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "baseline_run", "hello", cost=0.01)
    await _populate(es, ats, "current_run", "hello", cost=0.20)
    suite_thresholds = EvalThresholds(max_cost_delta=0.05)
    case = EvalCase(id="c1")
    result = await compare_case(case, "current_run", "baseline_run", suite_thresholds, es, ats)
    assert result.verdict == "fail"
    assert any("max_cost_delta" in v for v in result.violated_thresholds)


# ---------------------------------------------------------------------------
# fail — max_latency_delta_ms violated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fail_verdict_when_latency_exceeded():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "baseline_run", "hello", latency_ms=100)
    await _populate(es, ats, "current_run", "hello", latency_ms=60100)
    suite_thresholds = EvalThresholds(max_latency_delta_ms=1000)
    case = EvalCase(id="c1")
    result = await compare_case(case, "current_run", "baseline_run", suite_thresholds, es, ats)
    assert result.verdict == "fail"
    assert any("max_latency_delta_ms" in v for v in result.violated_thresholds)


# ---------------------------------------------------------------------------
# missing baseline run in store → graceful failure message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_graceful_when_baseline_run_missing_from_store():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "current_run", "hello")
    case = EvalCase(id="c1")
    result = await compare_case(
        case, "current_run", "nonexistent_baseline", EvalThresholds(), es, ats,
    )
    assert result.verdict == "fail"
    assert result.error is not None
    assert "nonexistent_baseline" in result.error


# ---------------------------------------------------------------------------
# case threshold overrides suite threshold (field-by-field merge)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case_threshold_overrides_suite():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    # Use identical content — similarity 1.0, no latency issue
    await _populate(es, ats, "baseline_run", "hello world", cost=0.01)
    await _populate(es, ats, "current_run", "hello world", cost=0.20)
    suite_thresholds = EvalThresholds(max_cost_delta=0.05)  # strict at suite level
    # Case overrides max_cost_delta to 1.00 — should pass
    case = EvalCase(id="c1", thresholds=EvalThresholds(max_cost_delta=1.00))
    result = await compare_case(case, "current_run", "baseline_run", suite_thresholds, es, ats)
    assert result.verdict == "pass"
    assert result.violated_thresholds == []


# ---------------------------------------------------------------------------
# violated_thresholds format: "field: actual < threshold"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_violated_threshold_message_format():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _populate(es, ats, "baseline_run", "The capital of France is Paris")
    await _populate(es, ats, "current_run", "banana mango tropical")
    case = EvalCase(id="c1", thresholds=EvalThresholds(min_similarity=0.90))
    result = await compare_case(case, "current_run", "baseline_run", EvalThresholds(), es, ats)
    assert result.violated_thresholds
    msg = result.violated_thresholds[0]
    assert "min_similarity" in msg
    assert "<" in msg
