"""Assertion model — post-execution contract checks on a node (issue #60).

An assertion is a *block-on* check evaluated after a node produces output. If it
fails, the node fails (like a schema-validation failure), so downstream nodes are
blocked. This turns a workflow into a regression safety net rather than a purely
diagnostic tool.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class Assertion(BaseModel):
    """A single post-execution check on a node's output or metrics.

    A node may declare several assertions; every one must pass. Within one
    assertion, every declared check must pass (logical AND) for it to pass.
    """

    name: str | None = None
    # Content checks (evaluated against the node's primary output artifact)
    contains: str | None = None       # output must contain this substring
    lacks: str | None = None          # output must NOT contain this substring
    matches: str | None = None        # output must match this regex (re.search)
    equals: str | None = None         # output must equal this string exactly
    min_length: int | None = None     # output length floor
    max_length: int | None = None     # output length ceiling
    # Metric checks
    cost_max: float | None = None     # node cost ceiling (same unit as budgets)
    latency_max_ms: int | None = None  # node wall-clock ceiling in ms
    # LLM-as-judge
    judge: str | None = None          # rubric; the judge answers PASS/FAIL
    judge_model: str | None = None    # model for the judge (default resolved by runner)

    @model_validator(mode="after")
    def _at_least_one_check(self) -> Assertion:
        checks = (
            self.contains, self.lacks, self.matches, self.equals,
            self.min_length, self.max_length, self.cost_max,
            self.latency_max_ms, self.judge,
        )
        if all(c is None for c in checks):
            raise ValueError(
                "assertion must declare at least one check "
                "(contains/lacks/matches/equals/min_length/max_length/"
                "cost_max/latency_max_ms/judge)"
            )
        if self.judge_model is not None and self.judge is None:
            raise ValueError("judge_model requires a judge rubric")
        return self

    def label(self) -> str:
        """A short human label for reports."""
        if self.name:
            return self.name
        for field in (
            "contains", "lacks", "matches", "equals", "min_length",
            "max_length", "cost_max", "latency_max_ms", "judge",
        ):
            val = getattr(self, field)
            if val is not None:
                return f"{field}={val!r}" if field != "judge" else "judge"
        return "assertion"


__all__ = ["Assertion"]
