from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

VALID_PATTERNS = frozenset({
    "critic", "debate", "best_of_n", "reflexion", "scatter",
    "fsm", "constitutional", "chain_of_verification", "plan_execute",
})

class StepConfig(BaseModel):
    prompt: str | None = None
    model: str | None = None
    max_retries: int | None = None

class PatternSpec(BaseModel):
    id: str
    pattern: str
    model: str
    system_prompt: str = ""
    config: dict[str, Any] = {}
    steps: dict[str, StepConfig] = {}
    depends_on: list[str] = []
    inputs: dict[str, Any] = {}
    outputs: list[str] = []
    budget: Any = None

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: str) -> str:
        if v not in VALID_PATTERNS:
            raise ValueError(f"Unknown pattern: {v}. Valid: {sorted(VALID_PATTERNS)}")
        return v
