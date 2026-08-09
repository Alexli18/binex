"""Tests for the pure helpers of trace/diff_rich.py.

The `_render_*` functions (rich Console output) are a conscious boundary —
see docs/contributing/testing.md; the boundary runs through the terminal,
not through the file, so the computational helpers are tested here.
"""

from __future__ import annotations

from binex.trace.diff_rich import (
    _build_diff_row,
    _detect_error_changes,
    _format_latency_delta,
)


def _step(**kwargs) -> dict:
    defaults = dict(
        agent_changed=False,
        agent_a="local://echo",
        agent_b="local://echo",
        artifacts_changed=False,
        status_changed=False,
        latency_a=100,
        latency_b=100,
        status_a="completed",
        status_b="completed",
    )
    defaults.update(kwargs)
    return defaults


class TestFormatLatencyDelta:
    def test_regression_colored_red_with_plus(self):
        lat_a, lat_b = _format_latency_delta(100, 250)

        assert lat_a == "100ms"
        assert lat_b == "250ms [red](+150ms)[/red]"

    def test_improvement_colored_green(self):
        _, lat_b = _format_latency_delta(250, 100)

        assert lat_b == "100ms [green](-150ms)[/green]"

    def test_zero_delta_green_with_plus_sign(self):
        _, lat_b = _format_latency_delta(100, 100)

        assert lat_b == "100ms [green](+0ms)[/green]"

    def test_missing_values_render_dash(self):
        assert _format_latency_delta(None, None) == ("-", "-")
        lat_a, lat_b = _format_latency_delta(None, 50)
        assert (lat_a, lat_b) == ("-", "50ms")


class TestDetectErrorChanges:
    def test_error_resolved(self):
        assert _detect_error_changes("boom", None) == "[green]error resolved[/green]"

    def test_new_error_truncated_to_30_chars(self):
        result = _detect_error_changes(None, "x" * 50)

        assert result == f"[red]new error: {'x' * 30}[/red]"

    def test_no_change_returns_none(self):
        assert _detect_error_changes(None, None) is None
        assert _detect_error_changes("same", "same") is None


class TestBuildDiffRow:
    def test_unchanged_step_has_no_changes_or_style(self):
        changes, sa, sb, _, _, style = _build_diff_row(_step())

        assert changes == []
        assert (sa, sb) == ("completed", "completed")
        assert style == ""

    def test_agent_change_listed(self):
        changes, *_ = _build_diff_row(
            _step(agent_changed=True, agent_a="llm://gpt-4o", agent_b="llm://gpt-4o-mini")
        )

        assert "agent: llm://gpt-4o -> llm://gpt-4o-mini" in changes

    def test_status_change_sets_yellow_row_style(self):
        *_, style = _build_diff_row(_step(status_changed=True))

        assert style == "yellow"

    def test_artifacts_and_error_changes_accumulate(self):
        changes, *_ = _build_diff_row(
            _step(artifacts_changed=True, error_a="boom", error_b=None)
        )

        assert "[yellow]artifacts changed[/yellow]" in changes
        assert "[green]error resolved[/green]" in changes

    def test_missing_statuses_render_dash(self):
        _, sa, sb, *_ = _build_diff_row(_step(status_a=None, status_b=None))

        assert (sa, sb) == ("-", "-")
