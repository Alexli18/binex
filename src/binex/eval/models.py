"""Pydantic v2 models for the eval subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EvalThresholds(BaseModel):
    """Comparison thresholds — None means the threshold is not enforced."""

    min_similarity: float | None = None
    max_cost_delta: float | None = None
    max_latency_delta_ms: int | None = None

    @field_validator("min_similarity")
    @classmethod
    def _check_similarity(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("min_similarity must be between 0.0 and 1.0")
        return v

    @field_validator("max_cost_delta")
    @classmethod
    def _check_cost(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("max_cost_delta must be >= 0")
        return v

    @field_validator("max_latency_delta_ms")
    @classmethod
    def _check_latency(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("max_latency_delta_ms must be >= 0")
        return v


class EvalAssert(BaseModel):
    """A single assertion on a case's output."""

    type: Literal["contains", "not_contains", "regex", "json_path", "llm_judge"]
    node: str | None = None

    # contains / not_contains
    value: str | None = None

    # regex
    pattern: str | None = None

    # json_path
    path: str | None = None
    exists: bool = True

    # llm_judge
    prompt: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def _validate_per_type(self) -> EvalAssert:
        t = self.type
        if t in ("contains", "not_contains") and self.value is None:
            raise ValueError(f"Assert of type '{t}' requires 'value'")
        if t == "regex" and self.pattern is None:
            raise ValueError("Assert of type 'regex' requires 'pattern'")
        if t == "json_path" and self.path is None:
            raise ValueError("Assert of type 'json_path' requires 'path'")
        if t == "llm_judge":
            if self.prompt is None:
                raise ValueError("Assert of type 'llm_judge' requires 'prompt'")
            if self.model is None:
                raise ValueError("Assert of type 'llm_judge' requires 'model'")
        return self


class EvalCase(BaseModel):
    """A single test case within an eval suite."""

    id: str
    inputs: dict[str, str] = Field(default_factory=dict)
    thresholds: EvalThresholds | None = None
    asserts: list[EvalAssert] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _non_empty_id(cls, v: str) -> str:
        if not v:
            raise ValueError("Case 'id' must be non-empty")
        return v


class EvalSuite(BaseModel):
    """Complete eval suite loaded from YAML."""

    name: str
    workflow: str
    thresholds: EvalThresholds = Field(default_factory=EvalThresholds)
    cases: list[EvalCase]

    @field_validator("name")
    @classmethod
    def _non_empty_name(cls, v: str) -> str:
        if not v:
            raise ValueError("Suite 'name' must be non-empty")
        return v

    @field_validator("workflow")
    @classmethod
    def _non_empty_workflow(cls, v: str) -> str:
        if not v:
            raise ValueError("Suite 'workflow' must be non-empty")
        return v

    @field_validator("cases")
    @classmethod
    def _validate_cases(cls, cases: list[EvalCase]) -> list[EvalCase]:
        if not cases:
            raise ValueError("Eval suite must define at least one case")
        seen: set[str] = set()
        for case in cases:
            if case.id in seen:
                raise ValueError(f"Duplicate case id '{case.id}'")
            seen.add(case.id)
        return cases


class AssertResult(BaseModel):
    """Result of evaluating a single EvalAssert."""

    assert_index: int
    type: str
    status: Literal["passed", "failed", "error"]
    reason: str


class EvalCaseResult(BaseModel):
    """Result of running a single eval case."""

    case_id: str
    verdict: Literal["pass", "fail", "no_baseline"]
    run_id: str | None = None
    baseline_run_id: str | None = None
    similarity: float | None = None
    cost_delta: float | None = None
    latency_delta_ms: int | None = None
    violated_thresholds: list[str] = Field(default_factory=list)
    assert_results: list[AssertResult] = Field(default_factory=list)
    error: str | None = None


class EvalResult(BaseModel):
    """Aggregated result for a full suite execution."""

    suite_name: str
    suite_path: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total: int
    passed: int
    failed: int
    no_baseline: int
    total_cost: float
    cases: list[EvalCaseResult]


__all__ = [
    "EvalThresholds",
    "EvalAssert",
    "EvalCase",
    "EvalSuite",
    "AssertResult",
    "EvalCaseResult",
    "EvalResult",
]
