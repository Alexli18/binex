"""Shared primitives for both eval entry points.

Binex has two places to write a check: a per-node ``assertions:`` block in the
workflow (enforced by the orchestrator on every run) and a per-case ``asserts:``
list in an eval suite. The two grew separately and disagreed on the one thing
they both depend on — how an artifact becomes text.

They now share this module, so a check means the same thing wherever it is
written. The schemas stay distinct on purpose: node assertions block a run,
suite asserts grade a case, and those are different jobs.

Everything here is pure (text in, verdict out); fetching artifacts lives with
the caller that owns the store.
"""

from __future__ import annotations

import json
import re
from typing import Any


def stringify(content: Any) -> str:
    """Render artifact content as the text a check runs against.

    JSON is canonical for structured content. It is what the user sees in the
    artifact files and in ``--json``, and it is the form a ``json_path`` assert
    can address. The alternative — Python's ``str(dict)`` — produces
    single-quoted, unparseable output, so ``contains: '"decision"'`` and
    ``contains: "'decision'"`` gave opposite verdicts depending on which of the
    two systems the check was written in.
    """
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if isinstance(content, dict | list):
        return json.dumps(content)
    # Scalars: json.dumps keeps `true`/`null` rather than Python's `True`/`None`,
    # which matters because the text is compared against YAML-authored literals.
    return json.dumps(content)


def check_contains(content: str, needle: str) -> bool:
    """True if *needle* occurs in *content*."""
    return needle in content


def check_not_contains(content: str, needle: str) -> bool:
    """True if *needle* is absent from *content*."""
    return needle not in content


def check_regex(content: str, pattern: str) -> bool:
    """True if *pattern* matches anywhere in *content* (``re.search``)."""
    return re.search(pattern, content) is not None


def check_equals(content: str, expected: str) -> bool:
    """True if *content* is exactly *expected*."""
    return content == expected


def check_min_length(content: str, minimum: int) -> bool:
    """True if *content* is at least *minimum* characters."""
    return len(content) >= minimum


def check_max_length(content: str, maximum: int) -> bool:
    """True if *content* is at most *maximum* characters."""
    return len(content) <= maximum


__all__ = [
    "check_contains",
    "check_equals",
    "check_max_length",
    "check_min_length",
    "check_not_contains",
    "check_regex",
    "stringify",
]
