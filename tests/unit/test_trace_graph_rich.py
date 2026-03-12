"""Tests for git-style DAG graph visualization in trace_rich."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from binex.models.execution import ExecutionRecord
from binex.models.task import TaskStatus
from binex.trace.trace_rich import format_trace_graph_rich


def _make_record(task_id: str, status: str = "completed", latency_ms: int = 1000) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"rec_{task_id}",
        run_id="run_001",
        task_id=task_id,
        agent_id=f"llm://{task_id}",
        status=TaskStatus(status),
        latency_ms=latency_ms,
        timestamp=datetime(2026, 3, 12, 10, 0, 0, tzinfo=UTC),
        trace_id="trace_001",
    )


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


class TestFormatTraceGraphRich:
    """Tests for format_trace_graph_rich git-style DAG renderer."""

    def test_single_node(self, capsys) -> None:
        """Single node with no edges renders without error."""
        records = [_make_record("A")]
        nodes = {"A": "llm://A"}
        edges: list[tuple[str, str]] = []

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "A" in captured.out
        assert "DAG" in captured.out

    def test_linear_chain(self, capsys) -> None:
        """A -> B -> C renders as a linear chain."""
        records = [_make_record("A"), _make_record("B"), _make_record("C")]
        nodes = {"A": "llm://A", "B": "llm://B", "C": "llm://C"}
        edges = [("A", "B"), ("B", "C")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "A" in captured.out
        assert "B" in captured.out
        assert "C" in captured.out
        # Should have continuation lines (│)
        assert "\u2502" in captured.out

    def test_fan_out(self, capsys) -> None:
        """A -> B, C shows fork lines."""
        records = [_make_record("A"), _make_record("B"), _make_record("C")]
        nodes = {"A": "llm://A", "B": "llm://B", "C": "llm://C"}
        edges = [("A", "B"), ("A", "C")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "A" in captured.out
        assert "B" in captured.out
        assert "C" in captured.out
        # Fork indicator ├ should appear
        assert "\u251c" in captured.out

    def test_fan_in(self, capsys) -> None:
        """B, C -> D shows merge lines."""
        records = [
            _make_record("B"), _make_record("C"), _make_record("D"),
        ]
        nodes = {"B": "llm://B", "C": "llm://C", "D": "llm://D"}
        edges = [("B", "D"), ("C", "D")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "D" in captured.out
        # Merge indicator ├ and ┘ should appear
        assert "\u251c" in captured.out
        assert "\u2518" in captured.out

    def test_diamond(self, capsys) -> None:
        """A -> B, C; B, C -> D (full diamond)."""
        records = [
            _make_record("A"), _make_record("B"),
            _make_record("C"), _make_record("D"),
        ]
        nodes = {"A": "llm://A", "B": "llm://B", "C": "llm://C", "D": "llm://D"}
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        for name in ("A", "B", "C", "D"):
            assert name in captured.out
        # Both fork and merge characters
        assert "\u251c" in captured.out

    def test_status_icons(self, capsys) -> None:
        """Different statuses show correct icons."""
        records = [
            _make_record("A", status="completed"),
            _make_record("B", status="failed"),
        ]
        nodes = {"A": "llm://A", "B": "llm://B"}
        edges = [("A", "B")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "\u2713" in captured.out  # checkmark
        assert "\u2717" in captured.out  # cross

    def test_latency_formatting(self, capsys) -> None:
        """Latency renders as ms or seconds depending on value."""
        records = [
            _make_record("A", latency_ms=500),
            _make_record("B", latency_ms=15000),
        ]
        nodes = {"A": "llm://A", "B": "llm://B"}
        edges = [("A", "B")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "500ms" in captured.out
        assert "15.0s" in captured.out

    def test_no_records(self, capsys) -> None:
        """Nodes without execution records show as pending."""
        records: list[ExecutionRecord] = []
        nodes = {"A": "llm://A", "B": "llm://B"}
        edges = [("A", "B")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        assert "pending" in captured.out

    def test_empty_dag(self, capsys) -> None:
        """Empty DAG with no nodes doesn't crash."""
        _run(format_trace_graph_rich([], {}, []))
        captured = capsys.readouterr()
        assert "DAG" in captured.out

    def test_wide_fan_out(self, capsys) -> None:
        """A -> B, C, D, E: four parallel branches."""
        records = [_make_record(n) for n in ("A", "B", "C", "D", "E")]
        nodes = {n: f"llm://{n}" for n in ("A", "B", "C", "D", "E")}
        edges = [("A", "B"), ("A", "C"), ("A", "D"), ("A", "E")]

        _run(format_trace_graph_rich(records, nodes, edges))
        captured = capsys.readouterr()
        for name in ("A", "B", "C", "D", "E"):
            assert name in captured.out
