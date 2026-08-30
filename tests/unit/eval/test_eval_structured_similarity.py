"""`min_similarity` inherits the field-wise comparison — pin what that changed.

Eval thresholds read `summary.content_similarity` from `diff_runs`, so moving
structured content off the character-level ratio moves eval's numbers with it.
Both directions matter and both are behaviour changes for existing suites:

* reordered keys used to score ~0.64 and fail a strict suite; they now score 1.0
* one changed field in a ten-field object used to score ~0.99 and pass a 0.95
  threshold; it now scores 0.90 and fails
"""

from __future__ import annotations

from typing import Any

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.diff import diff_runs


async def _summary_similarity(good: Any, bad: Any) -> float:
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    for run_id, content in (("baseline", good), ("candidate", bad)):
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=1, completed_nodes=1,
        ))
        await art_store.store(Artifact(
            id=f"art_{run_id}", run_id=run_id, type="result", content=content,
            lineage=Lineage(produced_by="n"),
        ))
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}", run_id=run_id, task_id="n",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            output_artifact_refs=[f"art_{run_id}"], latency_ms=10,
            trace_id=f"trace_{run_id}",
        ))
    result = await diff_runs(exec_store, art_store, "baseline", "candidate")
    return result["summary"]["content_similarity"]


@pytest.mark.asyncio
async def test_reordered_keys_satisfy_a_strict_threshold():
    """A suite with min_similarity: 1.0 must not fail on key order alone."""
    similarity = await _summary_similarity(
        {"verdict": "ok", "score": 3, "notes": "fine"},
        {"score": 3, "notes": "fine", "verdict": "ok"},
    )

    assert similarity == 1.0


@pytest.mark.asyncio
async def test_one_changed_field_is_proportional_not_diluted():
    """Ten fields, one changed — 0.9, not the ~0.99 a char ratio would give."""
    baseline = {f"field_{i}": i for i in range(10)}
    candidate = {**baseline, "field_3": 999}

    similarity = await _summary_similarity(baseline, candidate)

    assert similarity == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_long_context_no_longer_hides_a_changed_field():
    """Padding used to push a real change to ~0.999 and slip past any threshold."""
    filler = "Additional report context. " * 40
    similarity = await _summary_similarity(
        {"growth_pct": 12, "notes": filler},
        {"growth_pct": 21, "notes": filler},
    )

    assert similarity == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_text_output_keeps_the_character_ratio():
    """Prose thresholds are unaffected — that path did not change."""
    similarity = await _summary_similarity(
        "The report is ready.", "The report is done.",
    )

    assert 0.0 < similarity < 1.0
