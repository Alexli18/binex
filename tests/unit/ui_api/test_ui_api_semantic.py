"""Semantic analysis from the web UI — estimate first, then run.

`diff --semantic` and `bisect --semantic` spend the user's tokens, so the CLI
prints an estimate and asks before any call. The browser must not be a way
around that: the API exposes the estimate as its own endpoint so the UI can show
it and get an explicit confirmation, and only then sends `semantic: true`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus

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

PROSE = (
    "The report is ready. Revenue grew 12% this quarter.",
    "The report is done. Revenue increased 12% over the quarter.",
)


async def _seed(stores, nodes: dict[str, tuple[Any, Any]]) -> None:
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


class _RecordingJudge:
    def __init__(self, answers: dict[str, Any]) -> None:
        self._answers = answers
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, a: str, b: str) -> dict[str, Any]:
        self.calls.append((a, b))
        return self._answers


def _patched(module: str, judge: Any):
    """Patch the store lookup and the judge factory for one API module."""
    return (
        patch(f"binex.ui.api.{module}._get_stores"),
        patch("binex.trace.semantic_judge.make_semantic_judge", return_value=judge),
    )


# ---------------------------------------------------------------------------
# Estimate endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bisect_estimate_counts_differing_text_nodes(client, stores):
    await _seed(stores, {"draft": PROSE})

    with patch("binex.ui.api.bisect._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/bisect/estimate", json={"good_run": "good", "bad_run": "bad"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["calls"] == 1
    assert body["total_tokens"] > 0
    assert body["model"]
    assert "cost" in body


@pytest.mark.asyncio
async def test_bisect_estimate_ignores_structured_nodes(client, stores):
    """Field-wise comparison is exact and free — it must never be quoted."""
    await _seed(stores, {"review": ({"decision": "approved"}, {"decision": "rejected"})})

    with patch("binex.ui.api.bisect._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/bisect/estimate", json={"good_run": "good", "bad_run": "bad"},
        )

    assert resp.json()["calls"] == 0


@pytest.mark.asyncio
async def test_diff_estimate_counts_changed_text_nodes(client, stores):
    await _seed(stores, {"draft": PROSE})

    with patch("binex.ui.api.diff._get_stores", return_value=stores):
        resp = await client.post(
            "/api/v1/diff/estimate", json={"run_a": "good", "run_b": "bad"},
        )

    assert resp.status_code == 200
    assert resp.json()["calls"] == 1


# ---------------------------------------------------------------------------
# Running with a judge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bisect_semantic_clears_a_cosmetic_node(client, stores):
    """0.44 similarity would be flagged; the judge says it is a reword."""
    await _seed(stores, {"draft": PROSE})
    judge = _RecordingJudge(COSMETIC)

    stores_patch, judge_patch = _patched("bisect", judge)
    with stores_patch as m, judge_patch:
        m.return_value = stores
        resp = await client.post("/api/v1/bisect", json={
            "good_run": "good", "bad_run": "bad", "semantic": True,
        })

    assert resp.status_code == 200
    body = resp.json()
    assert len(judge.calls) == 1
    assert body["divergence_node"] is None
    assert "cosmetic" in body["node_map"][0]["semantic_verdict"]


@pytest.mark.asyncio
async def test_bisect_semantic_flags_a_meaningful_node(client, stores):
    await _seed(stores, {"draft": PROSE})
    judge = _RecordingJudge(FACTS_CHANGED)

    stores_patch, judge_patch = _patched("bisect", judge)
    with stores_patch as m, judge_patch:
        m.return_value = stores
        resp = await client.post("/api/v1/bisect", json={
            "good_run": "good", "bad_run": "bad", "semantic": True,
        })

    body = resp.json()
    assert body["divergence_node"] == "draft"
    assert "facts" in body["details"]["semantic_reason"]


@pytest.mark.asyncio
async def test_bisect_without_the_flag_calls_no_judge(client, stores):
    await _seed(stores, {"draft": PROSE})
    judge = _RecordingJudge(COSMETIC)

    stores_patch, judge_patch = _patched("bisect", judge)
    with stores_patch as m, judge_patch:
        m.return_value = stores
        resp = await client.post(
            "/api/v1/bisect", json={"good_run": "good", "bad_run": "bad"},
        )

    assert judge.calls == []
    assert resp.json()["divergence_node"] == "draft"


@pytest.mark.asyncio
async def test_diff_semantic_returns_verdicts(client, stores):
    await _seed(stores, {"draft": PROSE})
    judge = _RecordingJudge(COSMETIC)

    stores_patch, judge_patch = _patched("diff", judge)
    with stores_patch as m, judge_patch:
        m.return_value = stores
        resp = await client.post("/api/v1/diff", json={
            "run_a": "good", "run_b": "bad", "semantic": True,
        })

    assert resp.status_code == 200
    semantic = resp.json()["semantic"]
    assert len(semantic) == 1
    assert semantic[0]["node_id"] == "draft"
    assert semantic[0]["meaningful"] is False
    assert "cosmetic" in semantic[0]["summary"]
    assert [q["key"] for q in semantic[0]["questions"]] == [
        "structure", "facts", "tone_format",
    ]


@pytest.mark.asyncio
async def test_diff_without_the_flag_has_no_semantic_key(client, stores):
    await _seed(stores, {"draft": PROSE})
    judge = _RecordingJudge(COSMETIC)

    stores_patch, judge_patch = _patched("diff", judge)
    with stores_patch as m, judge_patch:
        m.return_value = stores
        resp = await client.post(
            "/api/v1/diff", json={"run_a": "good", "run_b": "bad"},
        )

    assert judge.calls == []
    assert resp.json().get("semantic") is None
