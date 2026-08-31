"""Pure assertion evaluation — no I/O (issue #60).

Given a node's output content and metrics, evaluate a list of
:class:`~binex.models.assertion.Assertion` and report per-assertion outcomes.
The LLM-as-judge check is delegated to an injected async callable so this module
stays free of network/model concerns and fully unit-testable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from binex.eval import checks
from binex.models.assertion import Assertion

# (assertion, content) -> (passed, reason). The judge reads the rubric from
# ``assertion.judge`` and may honor ``assertion.judge_model``.
JudgeFn = Callable[[Assertion, str], Awaitable[tuple[bool, str]]]


@dataclass
class AssertionOutcome:
    """Result of evaluating one assertion against a node."""

    assertion: Assertion
    passed: bool
    detail: str

    @property
    def label(self) -> str:
        return self.assertion.label()


def _check_content(a: Assertion, content: str) -> str | None:
    """Return a failure detail for content checks, or None if all pass.

    The comparisons come from :mod:`binex.eval.checks`, shared with suite
    asserts, so `contains` means the same thing in both places.
    """
    if a.contains is not None and not checks.check_contains(content, a.contains):
        return f"output does not contain {a.contains!r}"
    if a.lacks is not None and not checks.check_not_contains(content, a.lacks):
        return f"output contains forbidden {a.lacks!r}"
    if a.matches is not None and not checks.check_regex(content, a.matches):
        return f"output does not match /{a.matches}/"
    if a.equals is not None and not checks.check_equals(content, a.equals):
        return f"output does not equal {a.equals!r}"
    if a.min_length is not None and not checks.check_min_length(content, a.min_length):
        return f"output length {len(content)} < min_length {a.min_length}"
    if a.max_length is not None and not checks.check_max_length(content, a.max_length):
        return f"output length {len(content)} > max_length {a.max_length}"
    return None


def _check_metrics(a: Assertion, cost: float, latency_ms: int) -> str | None:
    """Return a failure detail for metric checks, or None if all pass."""
    if a.cost_max is not None and cost > a.cost_max:
        return f"cost {cost:.6g} > cost_max {a.cost_max:.6g}"
    if a.latency_max_ms is not None and latency_ms > a.latency_max_ms:
        return f"latency {latency_ms}ms > latency_max_ms {a.latency_max_ms}ms"
    return None


def _stringify(content: object) -> str:
    """Normalize a node's output artifact content to text for content checks.

    Delegates to the shared renderer — this used to be `str(content)`, which
    produced single-quoted, unparseable output and made an identically-written
    check disagree with the same check in an eval suite.
    """
    return checks.stringify(content)


async def evaluate_assertions(
    assertions: list[Assertion],
    *,
    content: object,
    cost: float = 0.0,
    latency_ms: int = 0,
    judge: JudgeFn | None = None,
) -> list[AssertionOutcome]:
    """Evaluate every assertion; return one outcome each (order preserved).

    Within an assertion, checks run cheapest-first (content, then metrics, then
    the judge) and short-circuit on the first failure so an expensive judge is
    skipped when a substring check already fails.
    """
    text = _stringify(content)
    outcomes: list[AssertionOutcome] = []

    for a in assertions:
        detail = _check_content(a, text) or _check_metrics(a, cost, latency_ms)

        if detail is None and a.judge is not None:
            if judge is None:
                detail = "judge assertion declared but no judge is configured"
            else:
                passed, reason = await judge(a, text)
                if not passed:
                    detail = f"judge rejected: {reason}"

        outcomes.append(
            AssertionOutcome(
                assertion=a,
                passed=detail is None,
                detail=detail or "ok",
            )
        )

    return outcomes


def summarize_failures(outcomes: list[AssertionOutcome]) -> str:
    """Join failing-assertion details into a single error message."""
    fails = [o for o in outcomes if not o.passed]
    return "; ".join(f"{o.label}: {o.detail}" for o in fails)


__all__ = [
    "AssertionOutcome",
    "JudgeFn",
    "evaluate_assertions",
    "summarize_failures",
]
