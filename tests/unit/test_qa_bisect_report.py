"""QA tests for BisectReport — enhanced bisect output."""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from binex.cli.bisect import (
    _content_preview,
    _describe_change,
    _format_latency,
    _node_word,
)
from binex.cli.main import cli
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import (
    InMemoryArtifactStore,
    InMemoryExecutionStore,
)
from binex.trace.bisect import (
    BisectReport,
    ErrorContext,
    NodeComparison,
    bisect_report,
    bisect_report_to_dict,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rec(
    rec_id: str,
    run_id: str,
    task_id: str,
    status: TaskStatus = TaskStatus.COMPLETED,
    latency_ms: int = 100,
    error: str | None = None,
    output_refs: list[str] | None = None,
    input_refs: list[str] | None = None,
) -> ExecutionRecord:
    return ExecutionRecord(
        id=rec_id,
        run_id=run_id,
        task_id=task_id,
        agent_id="llm://test",
        status=status,
        latency_ms=latency_ms,
        trace_id="t1",
        error=error,
        output_artifact_refs=output_refs or [],
        input_artifact_refs=input_refs or [],
    )


def _run(
    run_id: str,
    workflow: str = "wf",
    status: str = "completed",
) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name=workflow,
        status=status,
        total_nodes=3,
    )


def _art(
    art_id: str, run_id: str, content: str, produced_by: str,
) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type="llm_response",
        content=content,
        lineage=Lineage(produced_by=produced_by),
    )


async def _setup_divergent() -> tuple[
    InMemoryExecutionStore, InMemoryArtifactStore,
]:
    """Good run: A->B->C all completed.
    Bad run: A completed, B failed (timeout), C skipped."""
    es = InMemoryExecutionStore()
    a_s = InMemoryArtifactStore()

    await es.create_run(_run("good", status="completed"))
    await es.create_run(_run("bad", status="failed"))

    # Good run records
    await es.record(_rec("g1", "good", "A", latency_ms=100))
    await es.record(_rec("g2", "good", "B", latency_ms=200))
    await es.record(_rec("g3", "good", "C", latency_ms=150))

    # Bad run records
    await es.record(_rec("b1", "bad", "A", latency_ms=110))
    await es.record(_rec(
        "b2", "bad", "B",
        status=TaskStatus.FAILED, latency_ms=30000,
        error="Connection timed out after 30s",
    ))
    await es.record(_rec(
        "b3", "bad", "C",
        status=TaskStatus.CANCELLED, latency_ms=0,
    ))

    return es, a_s


async def _setup_content_diff() -> tuple[
    InMemoryExecutionStore, InMemoryArtifactStore,
]:
    """Both runs completed, but node B has different content."""
    es = InMemoryExecutionStore()
    a_s = InMemoryArtifactStore()

    await es.create_run(_run("good", status="completed"))
    await es.create_run(_run("bad", status="completed"))

    await es.record(_rec(
        "g1", "good", "A", output_refs=["art_ga"],
    ))
    await es.record(_rec(
        "g2", "good", "B", output_refs=["art_gb"],
    ))

    await es.record(_rec(
        "b1", "bad", "A", output_refs=["art_ba"],
    ))
    await es.record(_rec(
        "b2", "bad", "B", output_refs=["art_bb"],
    ))

    # Same content for A
    await a_s.store(_art("art_ga", "good", "same data", "A"))
    await a_s.store(_art("art_ba", "bad", "same data", "A"))

    # Different content for B
    await a_s.store(_art(
        "art_gb", "good",
        "The article covers SEO basics\n"
        "including keyword research and backlinks",
        "B",
    ))
    await a_s.store(_art(
        "art_bb", "bad",
        "Error: API returned empty response",
        "B",
    ))

    return es, a_s


async def _setup_identical() -> tuple[
    InMemoryExecutionStore, InMemoryArtifactStore,
]:
    """Two identical runs — no divergence."""
    es = InMemoryExecutionStore()
    a_s = InMemoryArtifactStore()

    for rid in ("good", "bad"):
        await es.create_run(_run(rid))
        await es.record(_rec(f"r1_{rid}", rid, "A"))
        await es.record(_rec(f"r2_{rid}", rid, "B"))

    return es, a_s


# ===========================================================================
# bisect_report() — unit tests
# ===========================================================================


class TestBisectReportFunction:

    @pytest.mark.asyncio
    async def test_identical_runs_no_divergence(self):
        es, a_s = await _setup_identical()
        report = await bisect_report(es, a_s, "good", "bad")

        assert report.divergence_point is None
        assert report.workflow_name == "wf"
        assert len(report.node_map) == 2
        assert all(nc.status == "match" for nc in report.node_map)
        assert all(nc.content_diff is None for nc in report.node_map)
        assert report.error_context is None
        assert report.downstream_impact == []

    @pytest.mark.asyncio
    async def test_status_divergence_with_error(self):
        es, a_s = await _setup_divergent()
        report = await bisect_report(es, a_s, "good", "bad")

        assert report.divergence_point is not None
        dp = report.divergence_point
        assert dp.node_id == "B"
        assert dp.divergence_type == "status"
        assert dp.good_status == "completed"
        assert dp.bad_status == "failed"

    @pytest.mark.asyncio
    async def test_error_context_populated(self):
        es, a_s = await _setup_divergent()
        report = await bisect_report(es, a_s, "good", "bad")

        assert report.error_context is not None
        assert report.error_context.node_id == "B"
        assert "timed out" in report.error_context.error_message
        assert report.error_context.pattern == "timeout"

    @pytest.mark.asyncio
    async def test_downstream_impact(self):
        es, a_s = await _setup_divergent()
        report = await bisect_report(es, a_s, "good", "bad")

        assert "C" in report.downstream_impact

    @pytest.mark.asyncio
    async def test_node_map_complete(self):
        es, a_s = await _setup_divergent()
        report = await bisect_report(es, a_s, "good", "bad")

        assert len(report.node_map) == 3
        by_id = {nc.node_id: nc for nc in report.node_map}

        assert by_id["A"].status == "match"
        assert by_id["A"].latency_good_ms == 100
        assert by_id["A"].latency_bad_ms == 110

        assert by_id["B"].status == "status_diff"
        assert by_id["B"].latency_bad_ms == 30000

        assert by_id["C"].status == "status_diff"

    @pytest.mark.asyncio
    async def test_content_divergence_with_diff(self):
        es, a_s = await _setup_content_diff()
        report = await bisect_report(es, a_s, "good", "bad")

        dp = report.divergence_point
        assert dp is not None
        assert dp.node_id == "B"
        assert dp.divergence_type == "content"
        assert dp.similarity is not None
        assert dp.similarity < 0.9

    @pytest.mark.asyncio
    async def test_content_diff_lines(self):
        es, a_s = await _setup_content_diff()
        report = await bisect_report(es, a_s, "good", "bad")

        # Content diff is now per-node
        by_id = {nc.node_id: nc for nc in report.node_map}
        assert by_id["B"].content_diff is not None
        assert len(by_id["B"].content_diff) > 0
        diff_text = "\n".join(by_id["B"].content_diff)
        assert "---" in diff_text or "+++" in diff_text

    @pytest.mark.asyncio
    async def test_missing_run_raises(self):
        es = InMemoryExecutionStore()
        a_s = InMemoryArtifactStore()
        with pytest.raises(ValueError, match="not found"):
            await bisect_report(es, a_s, "nope", "bad")

    @pytest.mark.asyncio
    async def test_mismatched_workflow_raises(self):
        es = InMemoryExecutionStore()
        a_s = InMemoryArtifactStore()
        await es.create_run(_run("good", workflow="wf_a"))
        await es.create_run(_run("bad", workflow="wf_b"))
        with pytest.raises(ValueError, match="don't match"):
            await bisect_report(es, a_s, "good", "bad")

    @pytest.mark.asyncio
    async def test_no_error_context_when_no_error(self):
        es, a_s = await _setup_content_diff()
        report = await bisect_report(es, a_s, "good", "bad")
        # Content divergence without error message
        assert report.error_context is None


# ===========================================================================
# bisect_report_to_dict() — serialization tests
# ===========================================================================


class TestBisectReportToDict:

    def test_full_report_serialization(self):
        report = BisectReport(
            good_run_id="g1",
            bad_run_id="b1",
            workflow_name="wf",
            divergence_point=None,
            node_map=[
                NodeComparison(
                    "A", "match", "completed", "completed",
                    similarity=1.0,
                    latency_good_ms=100, latency_bad_ms=110,
                ),
            ],
            error_context=None,
            downstream_impact=[],
        )
        d = bisect_report_to_dict(report)
        assert d["workflow_name"] == "wf"
        assert d["divergence"] is None
        assert d["message"] == "No divergence found"
        assert len(d["node_map"]) == 1
        assert d["node_map"][0]["status"] == "match"
        assert d["node_map"][0]["content_diff"] is None
        assert d["error_context"] is None
        assert d["downstream_impact"] == []

    def test_report_with_error_context(self):
        report = BisectReport(
            good_run_id="g1",
            bad_run_id="b1",
            workflow_name="wf",
            divergence_point=None,
            error_context=ErrorContext(
                node_id="B",
                error_message="timeout",
                pattern="timeout",
            ),
        )
        d = bisect_report_to_dict(report)
        assert d["error_context"]["node_id"] == "B"
        assert d["error_context"]["pattern"] == "timeout"

    def test_serialization_is_json_safe(self):
        report = BisectReport(
            good_run_id="g1",
            bad_run_id="b1",
            workflow_name="wf",
            divergence_point=None,
            node_map=[
                NodeComparison(
                    "A", "content_diff", "completed", "completed",
                    content_diff=["--- good", "+++ bad", "@@ -1 +1 @@"],
                ),
            ],
        )
        d = bisect_report_to_dict(report)
        # Should not raise
        json.dumps(d, default=str)
        assert d["node_map"][0]["content_diff"] is not None


# ===========================================================================
# CLI integration tests
# ===========================================================================


@pytest.fixture
def runner():
    return CliRunner()


class TestCLIBisectReport:

    def test_json_output_has_node_map(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_divergent())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli, ["bisect", "good", "bad", "--json"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "node_map" in data
        assert "error_context" in data
        assert "downstream_impact" in data
        assert data["workflow_name"] == "wf"
        assert len(data["node_map"]) == 3
        # Each node_map entry has content_diff key
        for nm in data["node_map"]:
            assert "content_diff" in nm

    def test_plain_output_shows_all_sections(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_divergent())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich"],
            )
        assert result.exit_code == 0
        out = result.output
        assert "Workflow: wf" in out
        assert "Divergence at: B" in out
        assert "Error:" in out
        assert "timed out" in out
        assert "Pattern: timeout" in out
        assert "Downstream Impact:" in out
        assert "Node Map:" in out

    def test_identical_runs_plain(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_identical())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli,
                ["bisect", "good", "bad", "--no-rich"],
            )
        assert result.exit_code == 0
        assert "No divergence" in result.output
        assert "2 match" in result.output

    def test_json_content_diff_present(self, runner):
        import asyncio

        es, a_s = asyncio.run(_setup_content_diff())
        with (
            __import__("unittest.mock", fromlist=["patch"]).patch(
                "binex.cli.bisect._get_stores",
                return_value=(es, a_s),
            )
        ):
            result = runner.invoke(
                cli, ["bisect", "good", "bad", "--json"],
            )
        assert result.exit_code == 0
        data = json.loads(result.output)
        # Content diff is per-node now
        b_node = [
            nm for nm in data["node_map"] if nm["node_id"] == "B"
        ][0]
        assert b_node["content_diff"] is not None
        assert len(b_node["content_diff"]) > 0


# ===========================================================================
# Formatting helpers — unit tests
# ===========================================================================


class TestBisectHelpers:

    def test_content_preview_short(self):
        assert _content_preview("hello") == "hello"

    def test_content_preview_truncates(self):
        text = "x" * 200
        result = _content_preview(text, limit=100)
        assert len(result) == 101  # 100 + ellipsis
        assert result.endswith("\u2026")

    def test_content_preview_first_line_only(self):
        text = "first line\nsecond line\nthird"
        result = _content_preview(text, limit=100)
        assert "\n" not in result
        assert result == "first line"

    def test_content_preview_none(self):
        assert _content_preview(None) == ""

    def test_describe_change_completely(self):
        assert _describe_change(0.1) == "completely changed"

    def test_describe_change_partially(self):
        assert _describe_change(0.5) == "partially changed"

    def test_describe_change_slightly(self):
        assert _describe_change(0.85) == "slightly changed"

    def test_describe_change_none(self):
        assert _describe_change(None) == "changed"

    def test_format_latency_ms(self):
        assert _format_latency(500) == "500ms"

    def test_format_latency_seconds(self):
        assert _format_latency(30000) == "30.0s"

    def test_format_latency_zero(self):
        assert _format_latency(0) == "skipped"

    def test_format_latency_none(self):
        assert _format_latency(None) == "-"

    def test_node_word_match(self):
        assert _node_word("match") == "ok"

    def test_node_word_content_diff(self):
        assert _node_word("content_diff") == "changed"

    def test_node_word_status_diff_failed(self):
        assert _node_word("status_diff", "failed") == "failed"

    def test_node_word_status_diff_cancelled(self):
        assert _node_word("status_diff", "cancelled") == "cancelled"

    def test_node_word_missing(self):
        assert _node_word("missing_in_good") == "new"
        assert _node_word("missing_in_bad") == "missing"
