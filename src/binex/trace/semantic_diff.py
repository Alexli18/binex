"""Semantic diff — tell "reworded the same answer" from "the answer changed" (#71).

Line-based diff of two LLM outputs is near-useless: the texts always differ.
This layer sits on top of the existing diff engine and asks a cheap model
**narrow, targeted questions** about each changed artifact pair — did the JSON
structure change? did factual claims change? did tone/format change? — rather
than one vague "did the meaning change".

The analysis is pure and takes an injected async ``judge`` callable, so it is
fully unit-testable without a model. The litellm-backed judge lives in
:mod:`binex.trace.semantic_judge`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

# Narrow rubric questions. Keys are stable (used in JSON + output); `meaningful`
# marks which ones constitute a substantive (non-cosmetic) change.
QUESTIONS: list[dict[str, Any]] = [
    {"key": "structure", "label": "structure/schema", "meaningful": True,
     "ask": "Did the data structure or JSON schema change "
            "(fields added/removed/renamed, types changed)?"},
    {"key": "facts", "label": "factual claims", "meaningful": True,
     "ask": "Did any factual claim, number, name, or conclusion change?"},
    {"key": "tone_format", "label": "tone/format", "meaningful": False,
     "ask": "Did only the wording, tone, or formatting change while the "
            "substance stayed the same?"},
]

_MEANINGFUL_KEYS = {q["key"] for q in QUESTIONS if q["meaningful"]}

# (content_a, content_b) -> {question_key: {"changed": bool, "confidence": str, "reason": str}}
SemanticJudgeFn = Callable[[str, str], Awaitable[dict[str, dict[str, Any]]]]


@dataclass
class QuestionVerdict:
    key: str
    changed: bool
    confidence: str  # "high" | "medium" | "low"
    reason: str


@dataclass
class NodeSemanticVerdict:
    node_id: str
    questions: list[QuestionVerdict] = field(default_factory=list)
    error: str | None = None

    @property
    def meaningful(self) -> bool:
        """True if a substantive (structure/facts) change was detected."""
        return any(q.changed and q.key in _MEANINGFUL_KEYS for q in self.questions)

    @property
    def summary(self) -> str:
        if self.error:
            return f"could not analyze ({self.error})"
        if self.meaningful:
            changed = [q.key for q in self.questions
                       if q.changed and q.key in _MEANINGFUL_KEYS]
            return "meaningful change: " + ", ".join(changed)
        if any(q.changed for q in self.questions):
            return "cosmetic only (reworded/reformatted, same substance)"
        return "semantically identical despite text diff"


def changed_pairs(diff_result: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extract (node_id, content_a, content_b) for nodes whose content differs.

    Only nodes with a real textual difference are candidates — identical or
    status-only changes never reach the (paid) judge.
    """
    pairs: list[tuple[str, str, str]] = []
    for step in diff_result.get("steps", []):
        a = step.get("content_a")
        b = step.get("content_b")
        if a is None and b is None:
            continue
        sa, sb = _stringify(a), _stringify(b)
        if sa == sb:
            continue
        if step.get("content_similarity", 1.0) >= 1.0 and not step.get("artifacts_changed"):
            continue
        pairs.append((step["task_id"], sa, sb))
    return pairs


def _stringify(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    return str(content)


def _parse_question(key: str, raw: dict[str, Any] | None) -> QuestionVerdict:
    """Coerce a judge's per-question answer into a QuestionVerdict, fail-safe."""
    if not isinstance(raw, dict):
        # Unknown → assume changed (conservative: never collapse what we can't read).
        return QuestionVerdict(key, changed=True, confidence="low",
                               reason="judge gave no answer")
    changed = bool(raw.get("changed", True))
    confidence = str(raw.get("confidence", "low")).lower()
    if confidence not in ("high", "medium", "low"):
        confidence = "low"
    reason = str(raw.get("reason", "")).strip() or "—"
    return QuestionVerdict(key, changed=changed, confidence=confidence, reason=reason)


async def analyze_pair(
    node_id: str, content_a: str, content_b: str, judge: SemanticJudgeFn,
) -> NodeSemanticVerdict:
    """Run the narrow-question judge on one artifact pair (fail-safe)."""
    try:
        answers = await judge(content_a, content_b)
    except Exception as exc:  # noqa: BLE001 — a judge error must not crash the diff
        return NodeSemanticVerdict(node_id=node_id, error=str(exc))
    questions = [_parse_question(q["key"], answers.get(q["key"])) for q in QUESTIONS]
    return NodeSemanticVerdict(node_id=node_id, questions=questions)


async def analyze_diff(
    diff_result: dict[str, Any], judge: SemanticJudgeFn,
) -> dict[str, NodeSemanticVerdict]:
    """Analyze every changed node in a diff result. Returns {node_id: verdict}."""
    verdicts: dict[str, NodeSemanticVerdict] = {}
    for node_id, a, b in changed_pairs(diff_result):
        verdicts[node_id] = await analyze_pair(node_id, a, b, judge)
    return verdicts


__all__ = [
    "QUESTIONS",
    "NodeSemanticVerdict",
    "QuestionVerdict",
    "SemanticJudgeFn",
    "analyze_diff",
    "analyze_pair",
    "changed_pairs",
]
