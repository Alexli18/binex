"""Tests for render_subtask_tree() and `binex trace subtasks` (cli/trace.py).

The grouping/rendering logic is pure (events in, string out) — only the
rich panel styling elsewhere in cli/trace.py is a conscious boundary.
"""

from __future__ import annotations

import json

from click.testing import CliRunner

from binex.cli.trace import render_subtask_tree, trace_subtasks_cmd


def _start(name: str) -> dict:
    return {"type": "task_start", "name": name}


def _end(name: str, status: str = "ok", duration: float = 1.5, error: str | None = None) -> dict:
    ev = {"type": "task_end", "name": name, "status": status, "duration_s": duration}
    if error:
        ev["error"] = error
    return ev


def test_empty_events_placeholder():
    assert render_subtask_tree([]) == "(no trace events)"


def test_completed_task_shows_check_and_duration():
    tree = render_subtask_tree([_start("fetch"), _end("fetch", duration=3.1)])

    assert "fetch" in tree
    assert "✅ 3.1s" in tree


def test_failed_task_shows_error_and_duration():
    tree = render_subtask_tree(
        [_start("parse"), _end("parse", status="error", duration=30.0, error="boom")]
    )

    assert "❌ boom (30.0s)" in tree


def test_task_without_end_marked_not_reached():
    tree = render_subtask_tree([_start("late")])

    assert "⏸ not reached" in tree


def test_children_attach_to_current_task():
    events = [
        _start("work"),
        {"type": "log", "message": "step one"},
        {"type": "checkpoint", "label": "half-way"},
        _end("work"),
    ]

    tree = render_subtask_tree(events)

    assert 'log: "step one"' in tree
    assert 'checkpoint: "half-way"' in tree


def test_orphan_children_before_first_task_ignored():
    events = [{"type": "log", "message": "orphan"}, _start("a"), _end("a")]

    tree = render_subtask_tree(events)

    assert "orphan" not in tree


def test_task_end_matched_by_name_only():
    # end for a different name must not close the current task
    events = [_start("a"), _end("b"), _start("c"), _end("c")]

    tree = render_subtask_tree(events)

    assert "⏸ not reached" in tree  # task "a" never ended
    assert "✅" in tree  # task "c" did


def test_tree_connectors_last_vs_middle():
    events = [_start("first"), _end("first"), _start("second"), _end("second")]

    lines = render_subtask_tree(events).splitlines()

    assert lines[0].startswith("├─")
    assert lines[1].startswith("└─")


# ---------------------------------------------------------------------------
# binex trace subtasks (file → parse → render)
# ---------------------------------------------------------------------------


def test_subtasks_command_renders_from_stderr_file(tmp_path):
    stderr_file = tmp_path / "stderr.log"
    events = [
        {"_binex_trace": True, "type": "task_start", "name": "fetch"},
        {"_binex_trace": True, "type": "task_end", "name": "fetch",
         "status": "ok", "duration_s": 2.0},
    ]
    stderr_file.write_text(
        "random noise\n" + "\n".join(json.dumps(e) for e in events) + "\n"
    )

    result = CliRunner().invoke(trace_subtasks_cmd, [str(stderr_file)])

    assert result.exit_code == 0
    assert "✅ 2.0s" in result.output


def test_subtasks_command_no_events_exits_1(tmp_path):
    stderr_file = tmp_path / "stderr.log"
    stderr_file.write_text("no trace here\n")

    result = CliRunner().invoke(trace_subtasks_cmd, [str(stderr_file)])

    assert result.exit_code == 1
    assert "No binex-trace events found" in result.output
