"""`bisect --semantic`: ask a model about text nodes instead of counting characters.

On prose the similarity ratio is not a weak signal, it is the wrong signal —
rewording scores ~0.44 (flagged) while inserting a "not" scores ~0.98 (passed).
No threshold separates those, so when a judge is supplied it decides every text
node that differs at all, and the ratio decides nothing.

Structured content never reaches the judge: the field-wise comparison is exact
and free.
"""

from __future__ import annotations

from typing import Any

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.bisect import bisect_report, find_divergence, semantic_candidates

# Judge answers keyed the way the rubric expects.
COSMETIC = {
    "structure": {"changed": False, "confidence": "high", "reason": "same shape"},
    "facts": {"changed": False, "confidence": "high", "reason": "same claims"},
    "tone_format": {"changed": True, "confidence": "high", "reason": "reworded"},
}
FACTS_CHANGED = {
    "structure": {"changed": False, "confidence": "high", "reason": "same shape"},
    "facts": {"changed": True, "confidence": "high", "reason": "verdict inverted"},
    "tone_format": {"changed": False, "confidence": "high", "reason": "same tone"},
}


class RecordingJudge:
    """Async judge stub that records the pairs it was asked about."""

    def __init__(self, answers: dict[str, Any] | list[dict[str, Any]]):
        self._answers = answers
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, a: str, b: str) -> dict[str, Any]:
        self.calls.append((a, b))
        if isinstance(self._answers, list):
            return self._answers[min(len(self.calls) - 1, len(self._answers) - 1)]
        return self._answers


class ExplodingJudge:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, a: str, b: str) -> dict[str, Any]:
        self.calls += 1
        raise RuntimeError("judge backend unavailable")


async def _seed(stores, nodes: dict[str, tuple[Any, Any]]) -> None:
    """Seed a linear pipeline; `nodes` maps node id -> (good content, bad content)."""
    exec_store, art_store = stores
    for run_id, index in (("good", 0), ("bad", 1)):
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=len(nodes), completed_nodes=len(nodes),
        ))
        previous: list[str] = []
        for node, contents in nodes.items():
            art_id = f"art_{run_id}_{node}"
            await art_store.store(Artifact(
                id=art_id, run_id=run_id, type="result", content=contents[index],
                lineage=Lineage(produced_by=node, derived_from=previous),
            ))
            await exec_store.record(ExecutionRecord(
                id=f"rec_{run_id}_{node}", run_id=run_id, task_id=node,
                agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
                input_artifact_refs=previous, output_artifact_refs=[art_id],
                latency_ms=10, trace_id=f"trace_{run_id}",
            ))
            previous = [art_id]


@pytest.fixture
def stores():
    return InMemoryExecutionStore(), InMemoryArtifactStore()


REWORDED = (
    "The report is ready. Revenue grew 12% this quarter.",
    "The report is done. Revenue increased 12% over the quarter.",
)
INVERTED = (
    "The candidate is suitable for the senior engineer role.",
    "The candidate is not suitable for the senior engineer role.",
)


@pytest.mark.asyncio
async def test_cosmetic_reword_is_not_a_divergence(stores):
    """Scores 0.442 — flagged by the threshold, cleared by the judge."""
    await _seed(stores, {"draft": REWORDED})
    judge = RecordingJudge(COSMETIC)

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert point is None
    assert len(judge.calls) == 1


@pytest.mark.asyncio
async def test_inverted_meaning_is_a_divergence(stores):
    """Scores ~0.98 — passed by the threshold, caught by the judge."""
    await _seed(stores, {"review": INVERTED})
    judge = RecordingJudge(FACTS_CHANGED)

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert point is not None
    assert point.node_id == "review"


@pytest.mark.asyncio
async def test_structured_content_never_reaches_the_judge(stores):
    """Field-wise comparison is exact — spending tokens on it would be waste."""
    await _seed(stores, {
        "review": ({"decision": "approved"}, {"decision": "rejected"}),
    })
    judge = RecordingJudge(COSMETIC)

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert point is not None
    assert judge.calls == []


@pytest.mark.asyncio
async def test_identical_text_never_reaches_the_judge(stores):
    await _seed(stores, {"draft": ("same output", "same output")})
    judge = RecordingJudge(COSMETIC)

    await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert judge.calls == []


@pytest.mark.asyncio
async def test_walk_stops_at_the_first_meaningful_divergence(stores):
    """Downstream nodes are consequences — judging them is paid-for noise."""
    await _seed(stores, {
        "first": INVERTED,
        "second": REWORDED,
        "third": REWORDED,
    })
    judge = RecordingJudge(FACTS_CHANGED)

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert point is not None
    assert point.node_id == "first"
    assert len(judge.calls) == 1


@pytest.mark.asyncio
async def test_cosmetic_nodes_are_skipped_and_the_walk_continues(stores):
    await _seed(stores, {"first": REWORDED, "second": INVERTED})
    judge = RecordingJudge([COSMETIC, FACTS_CHANGED])

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert point is not None
    assert point.node_id == "second"
    assert len(judge.calls) == 2


@pytest.mark.asyncio
async def test_judge_failure_falls_back_to_the_threshold(stores):
    """An unreachable judge must not silently turn every node into a match."""
    await _seed(stores, {"draft": REWORDED})
    judge = ExplodingJudge()

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert judge.calls == 1
    assert point is not None  # 0.442 is below the 0.9 threshold
    assert point.node_id == "draft"


@pytest.mark.asyncio
async def test_status_divergence_needs_no_judge(stores):
    exec_store, art_store = stores
    await _seed(stores, {"draft": REWORDED})
    bad = await exec_store.get_run("bad")
    assert bad is not None
    records = await exec_store.list_records("bad")
    records[0].status = TaskStatus.FAILED
    judge = RecordingJudge(COSMETIC)

    point = await find_divergence(*stores, "good", "bad", semantic_judge=judge)

    assert point is not None
    assert point.divergence_type == "status"
    assert judge.calls == []


@pytest.mark.asyncio
async def test_report_records_the_verdict(stores):
    await _seed(stores, {"draft": REWORDED})
    judge = RecordingJudge(COSMETIC)

    report = await bisect_report(*stores, "good", "bad", semantic_judge=judge)

    node = next(nc for nc in report.node_map if nc.node_id == "draft")
    assert node.status == "match"
    assert node.semantic_verdict is not None
    assert "cosmetic" in node.semantic_verdict


@pytest.mark.asyncio
async def test_candidates_list_only_differing_text_nodes(stores):
    """Drives the pre-flight cost estimate — it must not over- or under-count."""
    await _seed(stores, {
        "same": ("identical", "identical"),
        "structured": ({"a": 1}, {"a": 2}),
        "prose": REWORDED,
    })

    pairs = await semantic_candidates(*stores, "good", "bad")

    assert [node_id for node_id, _a, _b in pairs] == ["prose"]


@pytest.mark.asyncio
async def test_without_a_judge_behaviour_is_unchanged(stores):
    """--semantic is opt-in; the default path must not change."""
    await _seed(stores, {"draft": REWORDED})

    point = await find_divergence(*stores, "good", "bad")

    assert point is not None
    assert point.node_id == "draft"
    assert point.similarity is not None
