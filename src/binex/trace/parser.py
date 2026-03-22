"""Parse binex-trace events from stderr output."""

from __future__ import annotations

import json
from typing import Any

_TRACE_MARKER = '"_binex_trace"'


def parse_trace_events(stderr_lines: list[str]) -> list[dict[str, Any]]:
    """Extract and validate binex-trace JSON events from stderr lines.

    Each valid trace event is a JSON object containing ``{"_binex_trace": true}``.
    Non-trace lines and malformed JSON are silently skipped.
    """
    events: list[dict[str, Any]] = []
    for line in stderr_lines:
        line = line.strip()
        if not line or _TRACE_MARKER not in line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or not obj.get("_binex_trace"):
            continue
        if "type" not in obj:
            continue
        events.append(obj)
    return events
