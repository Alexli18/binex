"""Deterministic JSON repair — fix common malformed LLM output with zero tokens.

A large share of "invalid JSON" from models is not truly broken data: it's the
payload wrapped in a markdown code fence, or preceded by prose ("Here is the
JSON:"), or followed by a trailing comment. This module strips that packaging
and extracts the first balanced JSON value — before any model call is made.
See issue #65 (repair ladder, step 1).
"""

from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*\n?(.*?)```", re.S)


def _strip_fences(text: str) -> str:
    """Return the contents of the first markdown code fence, or the text as-is."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text


def _extract_balanced(text: str) -> str | None:
    """Extract the first balanced {...} or [...] value, respecting strings.

    Scans for the first ``{`` or ``[``, then walks forward tracking nesting
    depth while ignoring braces inside string literals (and their escapes).
    """
    start = None
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start is None:
        return None

    open_ch = text[start]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def repair_json_text(text: str) -> str | None:
    """Best-effort repair of malformed JSON text.

    Returns a string that parses as JSON, or ``None`` if it can't be recovered.
    Applies, in order: strip markdown fences, extract the first balanced value,
    then remove trailing commas.
    """
    if not isinstance(text, str):
        return None

    candidate = _strip_fences(text).strip()

    # If it already parses, nothing to repair.
    try:
        json.loads(candidate)
        return candidate
    except (json.JSONDecodeError, ValueError):
        pass

    extracted = _extract_balanced(candidate)
    if extracted is None:
        return None

    # Remove trailing commas before } or ] (a common model mistake).
    cleaned = re.sub(r",(\s*[}\]])", r"\1", extracted)

    try:
        json.loads(cleaned)
        return cleaned
    except (json.JSONDecodeError, ValueError):
        return None
