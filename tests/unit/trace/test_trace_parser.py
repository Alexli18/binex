"""Tests for trace/parser.py — the stderr trace-event filter."""

from __future__ import annotations

import json

from binex.trace.parser import parse_trace_events


def _event(**kwargs) -> str:
    payload = {"_binex_trace": True, "type": "task_start"}
    payload.update(kwargs)
    return json.dumps(payload)


def test_extracts_valid_events_in_order():
    lines = [_event(type="task_start", task="a"), _event(type="log", task="b")]

    events = parse_trace_events(lines)

    assert [e["type"] for e in events] == ["task_start", "log"]


def test_skips_lines_without_marker():
    lines = ["plain stderr noise", json.dumps({"type": "task_start"}), ""]

    assert parse_trace_events(lines) == []


def test_skips_malformed_json_with_marker():
    lines = ['{"_binex_trace": true, "type": broken', _event()]

    events = parse_trace_events(lines)

    assert len(events) == 1


def test_skips_marker_with_falsy_flag():
    lines = [json.dumps({"_binex_trace": False, "type": "log"}), _event()]

    assert len(parse_trace_events(lines)) == 1


def test_skips_non_dict_json():
    lines = ['["_binex_trace", true]', _event()]

    assert len(parse_trace_events(lines)) == 1


def test_skips_event_without_type():
    lines = [json.dumps({"_binex_trace": True}), _event()]

    events = parse_trace_events(lines)

    assert len(events) == 1
    assert events[0]["type"] == "task_start"


def test_strips_whitespace_around_lines():
    lines = ["   " + _event(type="checkpoint") + "  "]

    assert parse_trace_events(lines)[0]["type"] == "checkpoint"


def test_empty_input_returns_empty_list():
    assert parse_trace_events([]) == []
