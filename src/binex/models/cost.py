"""Cost tracking domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from binex.models.artifact import Artifact

CostSource = Literal[
    "llm_tokens",
    "llm_tokens_unavailable",
    "agent_report",
    "local",
    "unknown",
]


class CostRecord(BaseModel):
    """Individual cost event tied to a single node execution."""

    id: str
    run_id: str
    task_id: str
    cost: float = 0.0
    currency: str = "USD"
    source: CostSource
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str | None = None
    node_budget: float | None = None  # per-node budget limit (if set)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("cost")
    @classmethod
    def cost_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("cost must be >= 0")
        return v


class BudgetConfig(BaseModel):
    """Budget constraints for a workflow run."""

    max_cost: float
    currency: str = "USD"
    policy: Literal["stop", "warn"] = "warn"

    @field_validator("max_cost")
    @classmethod
    def max_cost_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("max_cost must be > 0")
        return v


class NodeCostHint(BaseModel):
    """Optional cost estimate for a node."""

    estimate: float = 0.0

    @field_validator("estimate")
    @classmethod
    def estimate_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("estimate must be >= 0")
        return v


class NodeBudget(BaseModel):
    """Per-node budget constraint. Policy inherited from workflow."""

    max_cost: float

    @field_validator("max_cost")
    @classmethod
    def max_cost_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("max_cost must be > 0")
        return v


class RunCostSummary(BaseModel):
    """Computed cost summary for a run (not persisted separately)."""

    run_id: str
    total_cost: float = 0.0
    currency: str = "USD"
    budget: float | None = None
    remaining_budget: float | None = None
    node_costs: dict[str, float] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Wrapper returned by adapters — carries artifacts and optional cost data."""

    artifacts: list[Artifact]
    cost: CostRecord | None = None


__all__ = [
    "BudgetConfig",
    "CostRecord",
    "CostSource",
    "ExecutionResult",
    "NodeBudget",
    "NodeCostHint",
    "RunCostSummary",
]
