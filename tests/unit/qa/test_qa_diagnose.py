"""QA tests for binex.trace.diagnose — TC-DIAG-001 through TC-DIAG-022."""

from __future__ import annotations

import pytest

from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.diagnose import (
    DiagnosticReport,
    LatencyAnomaly,
    RootCause,
    classify_error,
    detect_cascade,
    detect_latency_anomalies,
    diagnose_run,
    find_root_cause,
    generate_recommendations,
    report_to_dict,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    task_id: str,
    status: TaskStatus = TaskStatus.COMPLETED,
    latency_ms: int = 100,
    error: str | None = None,
    run_id: str = "run_01",
) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"rec_{task_id}",
        run_id=run_id,
        task_id=task_id,
        agent_id="llm://test",
        status=status,
        latency_ms=latency_ms,
        trace_id="trace_01",
        error=error,
    )


# ---------------------------------------------------------------------------
# TC-DIAG-001 .. TC-DIAG-007: classify_error
# ---------------------------------------------------------------------------

class TestClassifyError:
    """TC-DIAG-001 through TC-DIAG-007."""

    def test_timeout(self):
        """TC-DIAG-001: 'Connection timed out' -> timeout."""
        assert classify_error("Connection timed out") == "timeout"

    def test_rate_limit(self):
        """TC-DIAG-002: 'rate limit exceeded' -> rate_limit."""
        assert classify_error("rate limit exceeded") == "rate_limit"

    def test_auth(self):
        """TC-DIAG-003: 'unauthorized access' -> auth."""
        assert classify_error("unauthorized access") == "auth"

    def test_budget(self):
        """TC-DIAG-004: 'budget exceeded' -> budget."""
        assert classify_error("budget exceeded") == "budget"

    def test_connection(self):
        """TC-DIAG-005: 'connection refused' -> connection."""
        assert classify_error("connection refused") == "connection"

    def test_unknown(self):
        """TC-DIAG-006: 'some random error' -> unknown."""
        assert classify_error("some random error") == "unknown"

    def test_case_insensitive(self):
        """TC-DIAG-007: 'TIMEOUT' -> timeout (case insensitive)."""
        assert classify_error("TIMEOUT") == "timeout"

    def test_deadline_exceeded(self):
        """Extra: 'deadline exceeded' keyword triggers timeout."""
        assert classify_error("deadline exceeded on node A") == "timeout"

    def test_429_status(self):
        """Extra: '429' keyword triggers rate_limit."""
        assert classify_error("HTTP 429 response") == "rate_limit"

    def test_forbidden(self):
        """Extra: 'forbidden' keyword triggers auth."""
        assert classify_error("403 Forbidden") == "auth"

    def test_dns_unreachable(self):
        """Extra: 'dns' keyword triggers connection."""
        assert classify_error("DNS resolution failed") == "connection"

    def test_empty_string(self):
        """Extra: empty string -> unknown."""
        assert classify_error("") == "unknown"


# ---------------------------------------------------------------------------
# TC-DIAG-008 .. TC-DIAG-010: find_root_cause
# ---------------------------------------------------------------------------

class TestFindRootCause:
    """TC-DIAG-008 through TC-DIAG-010."""

    def test_no_failed_records(self):
        """TC-DIAG-008: No failed records returns None."""
        records = [
            _make_record("A"),
            _make_record("B"),
        ]
        assert find_root_cause(records, ["A", "B"]) is None

    def test_returns_first_failed_in_dag_order(self):
        """TC-DIAG-009: Returns first failed node according to dag_order."""
        records = [
            _make_record("A"),
            _make_record("B", status=TaskStatus.FAILED, error="Connection timed out"),
            _make_record("C", status=TaskStatus.FAILED, error="rate limit exceeded"),
        ]
        result = find_root_cause(records, ["A", "B", "C"])
        assert result is not None
        assert result.node_id == "B"
        assert result.pattern == "timeout"
        assert result.error_message == "Connection timed out"

    def test_dag_order_determines_root(self):
        """TC-DIAG-009b: DAG order (not record order) determines root cause."""
        records = [
            _make_record("C", status=TaskStatus.FAILED, error="rate limit"),
            _make_record("A"),
            _make_record("B", status=TaskStatus.FAILED, error="timeout"),
        ]
        # B appears before C in dag_order
        result = find_root_cause(records, ["A", "B", "C"])
        assert result is not None
        assert result.node_id == "B"

    def test_fallback_when_not_in_dag_order(self):
        """TC-DIAG-010: Falls back to first failed record when not in dag_order."""
        records = [
            _make_record("X", status=TaskStatus.FAILED, error="budget exceeded"),
        ]
        # dag_order doesn't contain X
        result = find_root_cause(records, ["A", "B"])
        assert result is not None
        assert result.node_id == "X"
        assert result.pattern == "budget"

    def test_error_none_defaults_to_unknown(self):
        """Extra: When error is None, defaults to 'unknown error' message."""
        records = [
            _make_record("A", status=TaskStatus.FAILED, error=None),
        ]
        result = find_root_cause(records, ["A"])
        assert result is not None
        assert result.error_message == "unknown error"
        assert result.pattern == "unknown"


# ---------------------------------------------------------------------------
# TC-DIAG-011 .. TC-DIAG-012: detect_cascade
# ---------------------------------------------------------------------------

class TestDetectCascade:
    """TC-DIAG-011 through TC-DIAG-012."""

    def test_without_dag_collects_failed(self):
        """TC-DIAG-011: Without DAG, collects all failed except root."""
        records = [
            _make_record("A", status=TaskStatus.FAILED, error="timeout"),
            _make_record("B", status=TaskStatus.FAILED, error="downstream"),
            _make_record("C"),
            _make_record("D", status=TaskStatus.FAILED, error="downstream"),
        ]
        affected = detect_cascade("A", records)
        assert "B" in affected
        assert "D" in affected
        assert "A" not in affected
        assert "C" not in affected

    def test_without_dag_excludes_completed(self):
        """TC-DIAG-011b: Without DAG, completed nodes are excluded."""
        records = [
            _make_record("root", status=TaskStatus.FAILED),
            _make_record("ok", status=TaskStatus.COMPLETED),
        ]
        affected = detect_cascade("root", records)
        assert affected == []

    def test_with_dag_bfs_walk(self):
        """TC-DIAG-012: With DAG object, does BFS via dependents()."""

        class FakeDAG:
            def dependents(self, node_id: str) -> list[str]:
                graph = {
                    "A": ["B", "C"],
                    "B": ["D"],
                    "C": [],
                    "D": [],
                }
                return graph.get(node_id, [])

        records = [
            _make_record("A", status=TaskStatus.FAILED, error="timeout"),
            _make_record("B", status=TaskStatus.FAILED, error="downstream"),
            _make_record("C", status=TaskStatus.FAILED, error="downstream"),
            _make_record("D", status=TaskStatus.FAILED, error="downstream"),
        ]
        affected = detect_cascade("A", records, dag=FakeDAG())
        assert "B" in affected
        assert "C" in affected
        assert "D" in affected
        assert "A" not in affected

    def test_with_dag_only_failed_nodes_collected(self):
        """TC-DIAG-012b: BFS walk only collects failed/skipped dependents."""

        class FakeDAG:
            def dependents(self, node_id: str) -> list[str]:
                return {"A": ["B", "C"], "B": [], "C": []}.get(node_id, [])

        records = [
            _make_record("A", status=TaskStatus.FAILED),
            _make_record("B", status=TaskStatus.COMPLETED),
            _make_record("C", status=TaskStatus.FAILED),
        ]
        affected = detect_cascade("A", records, dag=FakeDAG())
        # B is completed, so not in affected
        assert affected == ["C"]

    def test_with_dag_handles_cycles(self):
        """Extra: BFS visited set prevents infinite loops on cyclic graphs."""

        class CyclicDAG:
            def dependents(self, node_id: str) -> list[str]:
                return {"A": ["B"], "B": ["A"]}.get(node_id, [])

        records = [
            _make_record("A", status=TaskStatus.FAILED),
            _make_record("B", status=TaskStatus.FAILED),
        ]
        # Should not hang — BFS terminates via visited set.
        # Note: root node A can appear in affected when it's a dependent of B
        # in a cyclic graph, because the BFS doesn't explicitly exclude root.
        affected = detect_cascade("A", records, dag=CyclicDAG())
        assert "B" in affected
        assert len(affected) <= 2  # at most A and B

    def test_with_cancelled_status_not_collected_without_dag(self):
        """Extra: CANCELLED status is not in ('failed', 'skipped'), so excluded."""
        records = [
            _make_record("root", status=TaskStatus.FAILED),
            _make_record("other", status=TaskStatus.CANCELLED),
        ]
        affected = detect_cascade("root", records)
        assert affected == []


# ---------------------------------------------------------------------------
# TC-DIAG-013 .. TC-DIAG-015: detect_latency_anomalies
# ---------------------------------------------------------------------------

class TestDetectLatencyAnomalies:
    """TC-DIAG-013 through TC-DIAG-015."""

    def test_fewer_than_two_records(self):
        """TC-DIAG-013: Fewer than 2 positive-latency records -> empty."""
        records = [_make_record("A", latency_ms=100)]
        assert detect_latency_anomalies(records) == []

    def test_empty_records(self):
        """TC-DIAG-013b: No records at all -> empty."""
        assert detect_latency_anomalies([]) == []

    def test_flags_nodes_above_3x_median(self):
        """TC-DIAG-014: Flags nodes with latency > 3x median."""
        records = [
            _make_record("A", latency_ms=100),
            _make_record("B", latency_ms=100),
            _make_record("C", latency_ms=100),
            _make_record("D", latency_ms=500),  # 5x median=100
        ]
        anomalies = detect_latency_anomalies(records)
        assert len(anomalies) == 1
        assert anomalies[0].node_id == "D"
        assert anomalies[0].latency_ms == 500.0
        assert anomalies[0].median_ms == 100.0
        assert anomalies[0].ratio == 5.0

    def test_no_anomalies_when_all_similar(self):
        """TC-DIAG-014b: No anomalies when all latencies are similar."""
        records = [
            _make_record("A", latency_ms=100),
            _make_record("B", latency_ms=110),
            _make_record("C", latency_ms=90),
        ]
        assert detect_latency_anomalies(records) == []

    def test_skips_zero_latency(self):
        """TC-DIAG-015: Nodes with 0 latency are excluded from analysis."""
        records = [
            _make_record("A", latency_ms=0),
            _make_record("B", latency_ms=100),
            _make_record("C", latency_ms=100),
            _make_record("D", latency_ms=500),
        ]
        anomalies = detect_latency_anomalies(records)
        assert len(anomalies) == 1
        assert anomalies[0].node_id == "D"

    def test_zero_latency_node_not_flagged(self):
        """TC-DIAG-015b: A node with 0 latency is never flagged as anomaly."""
        records = [
            _make_record("A", latency_ms=0),
            _make_record("B", latency_ms=100),
            _make_record("C", latency_ms=200),
        ]
        anomalies = detect_latency_anomalies(records)
        node_ids = [a.node_id for a in anomalies]
        assert "A" not in node_ids

    def test_exactly_3x_not_flagged(self):
        """Extra: ratio must be > 3.0, not >= 3.0."""
        records = [
            _make_record("A", latency_ms=100),
            _make_record("B", latency_ms=100),
            _make_record("C", latency_ms=300),  # exactly 3x
        ]
        anomalies = detect_latency_anomalies(records)
        assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# TC-DIAG-016 .. TC-DIAG-018: generate_recommendations
# ---------------------------------------------------------------------------

class TestGenerateRecommendations:
    """TC-DIAG-016 through TC-DIAG-018."""

    def test_with_root_cause(self):
        """TC-DIAG-016: Root cause produces advice."""
        rc = RootCause(node_id="A", error_message="timed out", pattern="timeout")
        recs = generate_recommendations(rc, [])
        assert len(recs) == 1
        assert "Root cause" in recs[0]
        assert "'A'" in recs[0]
        assert "timeout" in recs[0]
        assert "increasing deadline" in recs[0]

    def test_with_anomalies(self):
        """TC-DIAG-017: Anomalies produce performance warnings."""
        anomaly = LatencyAnomaly(
            node_id="X", latency_ms=5000.0, median_ms=1000.0, ratio=5.0,
        )
        recs = generate_recommendations(None, [anomaly])
        assert len(recs) == 1
        assert "Node 'X'" in recs[0]
        assert "5.0x" in recs[0]
        assert "investigating performance" in recs[0]

    def test_none_root_cause_no_anomalies(self):
        """TC-DIAG-018: No root cause and no anomalies -> empty list."""
        recs = generate_recommendations(None, [])
        assert recs == []

    def test_both_root_cause_and_anomalies(self):
        """Extra: Both root cause and anomalies produce multiple recommendations."""
        rc = RootCause(node_id="A", error_message="rate limit", pattern="rate_limit")
        anomaly = LatencyAnomaly(
            node_id="B", latency_ms=4000.0, median_ms=1000.0, ratio=4.0,
        )
        recs = generate_recommendations(rc, [anomaly])
        assert len(recs) == 2
        assert "reducing parallelism" in recs[0]
        assert "Node 'B'" in recs[1]

    def test_all_patterns_produce_advice(self):
        """Extra: Each known pattern produces a relevant recommendation."""
        for pattern in ("timeout", "rate_limit", "auth", "budget", "connection", "unknown"):
            rc = RootCause(node_id="N", error_message="err", pattern=pattern)
            recs = generate_recommendations(rc, [])
            assert len(recs) == 1
            assert "Root cause" in recs[0]


# ---------------------------------------------------------------------------
# TC-DIAG-019 .. TC-DIAG-020: diagnose_run (async integration)
# ---------------------------------------------------------------------------

class TestDiagnoseRun:
    """TC-DIAG-019 through TC-DIAG-020."""

    @pytest.mark.asyncio
    async def test_clean_run(self):
        """TC-DIAG-019: Clean run returns status='clean'."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        summary = RunSummary(
            run_id="run_01",
            workflow_name="test_wf",
            status="completed",
            total_nodes=2,
            completed_nodes=2,
        )
        await exec_store.create_run(summary)
        await exec_store.record(_make_record("A"))
        await exec_store.record(_make_record("B"))

        report = await diagnose_run(exec_store, art_store, "run_01")
        assert report.status == "clean"
        assert report.root_cause is None
        assert report.affected_nodes == []
        assert report.latency_anomalies == []
        assert report.recommendations == []

    @pytest.mark.asyncio
    async def test_failed_run(self):
        """TC-DIAG-020: Failed run returns status='issues_found' with root_cause."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        summary = RunSummary(
            run_id="run_02",
            workflow_name="test_wf",
            status="failed",
            total_nodes=3,
            completed_nodes=1,
            failed_nodes=2,
        )
        await exec_store.create_run(summary)
        await exec_store.record(_make_record("A", run_id="run_02"))
        await exec_store.record(
            _make_record(
                "B", status=TaskStatus.FAILED,
                error="Connection timed out", run_id="run_02",
            ),
        )
        await exec_store.record(
            _make_record(
                "C", status=TaskStatus.FAILED,
                error="downstream failure", run_id="run_02",
            ),
        )

        report = await diagnose_run(exec_store, art_store, "run_02")
        assert report.status == "issues_found"
        assert report.root_cause is not None
        assert report.root_cause.node_id == "B"
        assert report.root_cause.pattern == "timeout"
        assert "C" in report.affected_nodes
        assert len(report.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_run_not_found(self):
        """Extra: diagnose_run raises ValueError for unknown run_id."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        with pytest.raises(ValueError, match="Run 'no_such_run' not found"):
            await diagnose_run(exec_store, art_store, "no_such_run")

    @pytest.mark.asyncio
    async def test_failed_run_with_latency_anomaly(self):
        """Extra: Report includes latency anomalies when present."""
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        summary = RunSummary(
            run_id="run_03",
            workflow_name="test_wf",
            status="failed",
            total_nodes=3,
            completed_nodes=2,
            failed_nodes=1,
        )
        await exec_store.create_run(summary)
        await exec_store.record(_make_record("A", latency_ms=100, run_id="run_03"))
        await exec_store.record(_make_record("B", latency_ms=100, run_id="run_03"))
        await exec_store.record(
            _make_record(
                "C",
                status=TaskStatus.FAILED,
                error="timeout",
                latency_ms=5000,
                run_id="run_03",
            ),
        )

        report = await diagnose_run(exec_store, art_store, "run_03")
        assert report.status == "issues_found"
        assert len(report.latency_anomalies) == 1
        assert report.latency_anomalies[0].node_id == "C"


# ---------------------------------------------------------------------------
# TC-DIAG-021 .. TC-DIAG-022: report_to_dict
# ---------------------------------------------------------------------------

class TestReportToDict:
    """TC-DIAG-021 through TC-DIAG-022."""

    def test_serializes_all_fields(self):
        """TC-DIAG-021: All fields serialized correctly."""
        rc = RootCause(node_id="A", error_message="timed out", pattern="timeout")
        anomaly = LatencyAnomaly(
            node_id="B", latency_ms=5000.0, median_ms=1000.0, ratio=5.0,
        )
        report = DiagnosticReport(
            run_id="run_01",
            status="issues_found",
            root_cause=rc,
            affected_nodes=["C", "D"],
            latency_anomalies=[anomaly],
            recommendations=["Fix timeout"],
        )
        d = report_to_dict(report)

        assert d["run_id"] == "run_01"
        assert d["status"] == "issues_found"
        assert d["root_cause"]["node_id"] == "A"
        assert d["root_cause"]["error_message"] == "timed out"
        assert d["root_cause"]["pattern"] == "timeout"
        assert d["affected_nodes"] == ["C", "D"]
        assert len(d["latency_anomalies"]) == 1
        assert d["latency_anomalies"][0]["node_id"] == "B"
        assert d["latency_anomalies"][0]["latency_ms"] == 5000.0
        assert d["latency_anomalies"][0]["median_ms"] == 1000.0
        assert d["latency_anomalies"][0]["ratio"] == 5.0
        assert d["recommendations"] == ["Fix timeout"]

    def test_none_root_cause(self):
        """TC-DIAG-022: None root_cause -> null in dict."""
        report = DiagnosticReport(run_id="run_01", status="clean")
        d = report_to_dict(report)

        assert d["root_cause"] is None
        assert d["affected_nodes"] == []
        assert d["latency_anomalies"] == []
        assert d["recommendations"] == []

    def test_empty_anomalies_list(self):
        """Extra: Empty anomalies list serializes to empty list."""
        rc = RootCause(node_id="A", error_message="err", pattern="unknown")
        report = DiagnosticReport(
            run_id="run_01",
            status="issues_found",
            root_cause=rc,
        )
        d = report_to_dict(report)
        assert d["latency_anomalies"] == []

    def test_multiple_anomalies(self):
        """Extra: Multiple anomalies all serialized."""
        anomalies = [
            LatencyAnomaly(node_id="X", latency_ms=4000.0, median_ms=1000.0, ratio=4.0),
            LatencyAnomaly(node_id="Y", latency_ms=5000.0, median_ms=1000.0, ratio=5.0),
        ]
        report = DiagnosticReport(
            run_id="r1",
            status="issues_found",
            latency_anomalies=anomalies,
        )
        d = report_to_dict(report)
        assert len(d["latency_anomalies"]) == 2
        assert d["latency_anomalies"][0]["node_id"] == "X"
        assert d["latency_anomalies"][1]["node_id"] == "Y"
