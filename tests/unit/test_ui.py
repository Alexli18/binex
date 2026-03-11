"""Tests for the shared UI design system (binex.cli.ui)."""

from __future__ import annotations

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from binex.cli.ui import (
    BORDER_STYLE,
    HEADER_STYLE,
    STATUS_CONFIG,
    cost_bar,
    get_console,
    make_header,
    make_panel,
    make_summary,
    make_table,
    plain_header,
    plain_status_icon,
    plain_summary,
    render_to_string,
    status_icon,
    status_text,
)


# ── Constants ────────────────────────────────────────────────────────────────

class TestConstants:
    def test_border_style(self):
        assert BORDER_STYLE == "blue"

    def test_header_style(self):
        assert HEADER_STYLE == "bold cyan"

    def test_status_config_has_all_keys(self):
        expected = {
            "completed", "failed", "running", "timed_out", "skipped",
            "over_budget", "ok", "missing", "error", "degraded",
            "unreachable", "timeout", "not_initialized",
        }
        assert set(STATUS_CONFIG.keys()) == expected

    def test_status_config_values_are_tuples(self):
        for key, val in STATUS_CONFIG.items():
            assert isinstance(val, tuple) and len(val) == 2, f"bad entry: {key}"


# ── status_icon ──────────────────────────────────────────────────────────────

class TestStatusIcon:
    def test_completed(self):
        result = status_icon("completed")
        assert "[green]●[/green]" == result

    def test_failed(self):
        result = status_icon("failed")
        assert "[red bold]●[/red bold]" == result

    def test_unknown_status(self):
        result = status_icon("something_weird")
        assert "[dim]●[/dim]" == result

    @pytest.mark.parametrize("status", list(STATUS_CONFIG.keys()))
    def test_all_known_statuses_return_markup(self, status):
        result = status_icon(status)
        assert "●" in result
        assert result.startswith("[")


# ── status_text ──────────────────────────────────────────────────────────────

class TestStatusText:
    def test_returns_text_object(self):
        result = status_text("completed")
        assert isinstance(result, Text)

    def test_completed_content(self):
        result = status_text("completed")
        assert result.plain == "completed"

    def test_failed_content(self):
        result = status_text("failed")
        assert result.plain == "FAILED"

    def test_unknown_uses_raw_name(self):
        result = status_text("banana")
        assert result.plain == "banana"


# ── make_summary ─────────────────────────────────────────────────────────────

class TestMakeSummary:
    def test_completed_only(self):
        t = make_summary(completed=4)
        assert "4 completed" in t.plain

    def test_failed_only(self):
        t = make_summary(failed=2)
        assert "2 failed" in t.plain

    def test_completed_and_failed(self):
        t = make_summary(completed=3, failed=1)
        text = t.plain
        assert "3 completed" in text
        assert "1 failed" in text

    def test_time_included(self):
        t = make_summary(completed=1, time=19.94)
        assert "19.94s" in t.plain

    def test_cost_included(self):
        t = make_summary(completed=1, cost=0.01)
        assert "$0.01" in t.plain

    def test_all_fields(self):
        t = make_summary(completed=4, failed=1, time=19.94, cost=0.01)
        text = t.plain
        assert "4 completed" in text
        assert "1 failed" in text
        assert "19.94s" in text
        assert "$0.01" in text

    def test_empty_summary(self):
        t = make_summary()
        assert t.plain == ""

    def test_separator_present(self):
        t = make_summary(completed=1, failed=1)
        assert " · " in t.plain


# ── make_header ──────────────────────────────────────────────────────────────

class TestMakeHeader:
    def test_single_field(self):
        t = make_header(workflow="test.yaml")
        assert "Workflow: test.yaml" in t.plain

    def test_multiple_fields(self):
        t = make_header(workflow="test.yaml", run="abc123")
        text = t.plain
        assert "Workflow: test.yaml" in text
        assert "Run: abc123" in text
        assert "·" in text

    def test_underscore_label(self):
        t = make_header(run_id="abc")
        assert "Run Id: abc" in t.plain

    def test_empty_header(self):
        t = make_header()
        assert t.plain == ""


# ── make_panel ───────────────────────────────────────────────────────────────

class TestMakePanel:
    def test_returns_panel(self):
        p = make_panel("hello")
        assert isinstance(p, Panel)

    def test_border_style(self):
        p = make_panel("hello")
        assert p.border_style == BORDER_STYLE

    def test_title(self):
        p = make_panel("hello", title="My Title")
        assert p.title == "My Title"

    def test_subtitle(self):
        p = make_panel("hello", subtitle="sub")
        assert p.subtitle == "sub"

    def test_padding(self):
        p = make_panel("hello")
        assert p.padding == (1, 2)


# ── make_table ───────────────────────────────────────────────────────────────

class TestMakeTable:
    def test_returns_table(self):
        t = make_table(("Name", {}), ("Value", {}))
        assert isinstance(t, Table)

    def test_columns_count(self):
        t = make_table(("A", {}), ("B", {}), ("C", {}))
        assert len(t.columns) == 3

    def test_column_names(self):
        t = make_table(("Name", {}), ("Age", {}))
        headers = [c.header for c in t.columns]
        assert headers == ["Name", "Age"]

    def test_title(self):
        t = make_table(("X", {}), title="My Table")
        assert t.title == "My Table"

    def test_column_kwargs_forwarded(self):
        t = make_table(("Val", {"justify": "right", "no_wrap": True}))
        col = t.columns[0]
        assert col.justify == "right"
        assert col.no_wrap is True

    def test_border_style(self):
        t = make_table(("X", {}))
        assert t.border_style == BORDER_STYLE

    def test_header_style(self):
        t = make_table(("X", {}))
        assert t.header_style == HEADER_STYLE


# ── cost_bar ─────────────────────────────────────────────────────────────────

class TestCostBar:
    def test_zero_value(self):
        bar = cost_bar(0, 100)
        assert "╌" in bar
        assert "━" not in bar

    def test_full_value(self):
        bar = cost_bar(100, 100)
        assert "━" in bar
        assert "╌" not in bar

    def test_partial_value(self):
        bar = cost_bar(50, 100, width=20)
        assert "━" in bar
        assert "╌" in bar

    def test_over_max_clamps(self):
        bar = cost_bar(200, 100, width=10)
        # Should be fully filled (clamped to 1.0)
        assert bar.count("━") == 10

    def test_zero_max(self):
        bar = cost_bar(50, 0)
        assert "╌" in bar
        assert "━" not in bar

    def test_negative_value(self):
        bar = cost_bar(-5, 100)
        assert "╌" in bar
        assert "━" not in bar

    def test_custom_width(self):
        bar = cost_bar(100, 100, width=30)
        assert bar.count("━") == 30


# ── plain_status_icon ────────────────────────────────────────────────────────

class TestPlainStatusIcon:
    @pytest.mark.parametrize(
        "status,expected",
        [
            ("completed", "✓"),
            ("ok", "✓"),
            ("failed", "✗"),
            ("error", "✗"),
            ("missing", "✗"),
            ("unreachable", "✗"),
            ("running", "!"),
            ("timed_out", "!"),
            ("over_budget", "!"),
            ("degraded", "!"),
            ("timeout", "!"),
            ("skipped", "○"),
            ("not_initialized", "·"),
        ],
    )
    def test_known_statuses(self, status, expected):
        assert plain_status_icon(status) == expected

    def test_unknown_status(self):
        assert plain_status_icon("unknown_xyz") == "?"


# ── plain_summary ────────────────────────────────────────────────────────────

class TestPlainSummary:
    def test_all_fields(self):
        s = plain_summary(completed=4, failed=1, time=19.94, cost=0.01)
        assert "✓ 4 completed" in s
        assert "✗ 1 failed" in s
        assert "19.94s" in s
        assert "$0.01" in s

    def test_empty(self):
        assert plain_summary() == ""

    def test_separator(self):
        s = plain_summary(completed=1, failed=1)
        assert " · " in s


# ── plain_header ─────────────────────────────────────────────────────────────

class TestPlainHeader:
    def test_single_field(self):
        s = plain_header(workflow="test.yaml")
        assert s == "Workflow: test.yaml"

    def test_multiple_fields(self):
        s = plain_header(workflow="test.yaml", run="abc")
        assert "Workflow: test.yaml" in s
        assert "Run: abc" in s
        assert "  ·  " in s


# ── get_console ──────────────────────────────────────────────────────────────

class TestGetConsole:
    def test_returns_console(self):
        c = get_console()
        assert isinstance(c, Console)

    def test_default_width(self):
        c = get_console()
        assert c.width == 120

    def test_custom_width(self):
        c = get_console(width=80)
        assert c.width == 80

    def test_stderr_variant(self):
        c = get_console(stderr=True)
        assert isinstance(c, Console)


# ── render_to_string ─────────────────────────────────────────────────────────

class TestRenderToString:
    def test_returns_string(self):
        result = render_to_string(Text("hello"))
        assert isinstance(result, str)

    def test_contains_content(self):
        result = render_to_string(Text("hello world"))
        assert "hello world" in result

    def test_panel_renders(self):
        p = make_panel("inside panel", title="Test")
        result = render_to_string(p)
        assert "inside panel" in result
        assert "Test" in result

    def test_custom_width(self):
        result_narrow = render_to_string(Text("x"), width=40)
        assert isinstance(result_narrow, str)
