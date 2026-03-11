"""Tests for rich-formatted debug report output."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from binex.trace.debug_report import DebugReport, NodeReport
from binex.trace.debug_rich import format_debug_report_rich


def _capture_rich(report, **kwargs) -> str:
    """Call format_debug_report_rich and capture its console output."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True, width=120)
    with patch("binex.trace.debug_rich.get_console", return_value=test_console):
        format_debug_report_rich(report, **kwargs)
    return buf.getvalue()


def _make_report(*, status="failed", nodes=None):
    return DebugReport(
        run_id="run-rich-001",
        workflow_name="test-wf",
        status=status,
        total_nodes=2,
        completed_nodes=1,
        failed_nodes=1,
        duration_ms=3000,
        nodes=nodes
        or [
            NodeReport(
                node_id="step_a",
                agent_id="llm://gpt-4",
                status="completed",
                latency_ms=100,
                prompt="Plan",
            ),
            NodeReport(
                node_id="step_b",
                agent_id="llm://gpt-4",
                status="failed",
                latency_ms=200,
                prompt="Execute",
                error="Connection refused",
            ),
        ],
    )


# --- T039: test_rich_format_returns_string ---


def test_rich_format_returns_string():
    """Rich formatter returns string containing run_id and node IDs."""
    report = _make_report()
    output = _capture_rich(report)

    assert isinstance(output, str)
    assert "run-rich-001" in output
    assert "step_a" in output
    assert "step_b" in output


# --- T040: test_rich_format_errors_only ---


def test_rich_format_errors_only():
    """Rich formatter with errors_only shows only failed nodes."""
    report = _make_report()
    output = _capture_rich(report, errors_only=True)

    assert "step_b" in output
    assert "Connection refused" in output
    # step_a (completed) should not appear as a node panel
    # It may appear in the header summary but not as a separate node section
    lines = output.split("\n")
    # Check that step_a doesn't appear in any panel title
    panel_lines = [l for l in lines if "step_a" in l and "completed" in l]
    assert len(panel_lines) == 0
