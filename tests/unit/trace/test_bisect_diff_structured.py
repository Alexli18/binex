"""bisect and diff must use the field-wise comparison for structured artifacts."""

from __future__ import annotations

from typing import Any

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.bisect import bisect_report, find_divergence
from binex.trace.diff import diff_runs


async def _two_runs(
    good_content: Any, bad_content: Any,
) -> tuple[InMemoryExecutionStore, InMemoryArtifactStore]:
    """Two completed single-node runs whose node 'n' produced the given content."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    for run_id, content in (("good", good_content), ("bad", bad_content)):
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=1, completed_nodes=1,
        ))
        art_id = f"art_{run_id}"
        await art_store.store(Artifact(
            id=art_id, run_id=run_id, type="result", content=content,
            lineage=Lineage(produced_by="n"),
        ))
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}", run_id=run_id, task_id="n",
            agent_id="local://echo", status=TaskStatus.COMPLETED,
            output_artifact_refs=[art_id], latency_ms=10,
            trace_id=f"trace_{run_id}",
        ))
    return exec_store, art_store


class TestBisect:
    @pytest.mark.asyncio
    async def test_reordered_keys_are_not_a_divergence(self):
        """Previously scored 0.636 and reported as the divergence point."""
        exec_store, art_store = await _two_runs(
            {"revenue": 12, "costs": 3, "verdict": "ok"},
            {"verdict": "ok", "costs": 3, "revenue": 12},
        )

        assert await find_divergence(exec_store, art_store, "good", "bad") is None

    @pytest.mark.asyncio
    async def test_flipped_verdict_is_a_divergence(self):
        """Previously scored 0.915 and passed as a match."""
        exec_store, art_store = await _two_runs(
            {"decision": "approved", "reason": "all checks passed"},
            {"decision": "rejected", "reason": "all checks passed"},
        )

        point = await find_divergence(exec_store, art_store, "good", "bad")

        assert point is not None
        assert point.node_id == "n"
        assert point.divergence_type == "content"

    @pytest.mark.asyncio
    async def test_diluted_numeric_change_is_a_divergence(self):
        """Long context used to push a real change to 0.999 and hide it."""
        filler = "Additional report context. " * 40
        exec_store, art_store = await _two_runs(
            {"growth_pct": 12, "notes": filler},
            {"growth_pct": 21, "notes": filler},
        )

        point = await find_divergence(exec_store, art_store, "good", "bad")

        assert point is not None

    @pytest.mark.asyncio
    async def test_report_names_the_changed_field(self):
        """The output must say which field moved, not just a ratio."""
        exec_store, art_store = await _two_runs(
            {"decision": "approved", "reason": "all checks passed"},
            {"decision": "rejected", "reason": "all checks passed"},
        )

        report = await bisect_report(exec_store, art_store, "good", "bad")

        node = next(nc for nc in report.node_map if nc.node_id == "n")
        assert node.status == "content_diff"
        rendered = "\n".join(node.content_diff or [])
        assert "decision" in rendered
        assert "approved" in rendered
        assert "rejected" in rendered

    @pytest.mark.asyncio
    async def test_prose_still_uses_text_similarity(self):
        """Free-form text keeps the old behaviour — that is item (2)'s problem."""
        exec_store, art_store = await _two_runs(
            "The quick brown fox jumps over the lazy dog",
            "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
        )

        point = await find_divergence(exec_store, art_store, "good", "bad")

        assert point is not None
        assert point.similarity is not None
        assert point.similarity < 0.9


class TestDiff:
    @pytest.mark.asyncio
    async def test_reordered_keys_score_identical(self):
        exec_store, art_store = await _two_runs(
            {"revenue": 12, "costs": 3},
            {"costs": 3, "revenue": 12},
        )

        result = await diff_runs(exec_store, art_store, "good", "bad")

        step = result["steps"][0]
        assert step["content_similarity"] == 1.0
        assert step["field_changes"] == []
        assert result["summary"]["changed_nodes"] == 0

    @pytest.mark.asyncio
    async def test_identical_structure_offers_no_diff_to_render(self):
        """`artifact_diff` drives the UI's "changed" affordance.

        Falling back to a text diff of the stringified mappings would put the
        false positive straight back: reordered keys differ as text.
        """
        exec_store, art_store = await _two_runs(
            {"revenue": 12, "costs": 3},
            {"costs": 3, "revenue": 12},
        )

        result = await diff_runs(exec_store, art_store, "good", "bad")

        assert result["steps"][0]["artifact_diff"] is None

    @pytest.mark.asyncio
    async def test_changed_field_diff_is_the_field_lines(self):
        exec_store, art_store = await _two_runs(
            {"decision": "approved"}, {"decision": "rejected"},
        )

        result = await diff_runs(exec_store, art_store, "good", "bad")

        artifact_diff = result["steps"][0]["artifact_diff"]
        assert artifact_diff is not None
        assert "decision" in artifact_diff
        assert "@@" not in artifact_diff  # not a unified diff

    @pytest.mark.asyncio
    async def test_changed_field_is_listed(self):
        exec_store, art_store = await _two_runs(
            {"is_safe": True, "score": 0.91},
            {"is_safe": False, "score": 0.91},
        )

        result = await diff_runs(exec_store, art_store, "good", "bad")

        step = result["steps"][0]
        assert step["content_similarity"] < 1.0
        assert step["field_changes"] == [
            {"path": "is_safe", "before": True, "after": False, "kind": "changed"},
        ]
        assert result["summary"]["changed_nodes"] == 1

    @pytest.mark.asyncio
    async def test_field_changes_are_structured_not_prerendered(self):
        """Consumers (jq, the web UI) must not have to re-parse a rendered line."""
        exec_store, art_store = await _two_runs(
            {"totals": {"q1": 10}}, {"totals": {"q1": 99}},
        )

        result = await diff_runs(exec_store, art_store, "good", "bad")

        change = result["steps"][0]["field_changes"][0]
        assert change["path"] == "totals.q1"
        assert change["before"] == 10
        assert change["after"] == 99
        assert change["kind"] == "changed"

    @pytest.mark.asyncio
    async def test_field_changes_absent_for_text_content(self):
        """Text content has no field-level detail to offer."""
        exec_store, art_store = await _two_runs("hello there", "hello world")

        result = await diff_runs(exec_store, art_store, "good", "bad")

        assert result["steps"][0]["field_changes"] is None
