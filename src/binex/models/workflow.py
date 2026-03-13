"""WorkflowSpec, NodeSpec, and DefaultsSpec domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from binex.models.cost import BudgetConfig, NodeBudget, NodeCostHint
from binex.models.task import RetryPolicy


class BackEdge(BaseModel):
    """Conditional back-edge: re-execute upstream nodes on condition."""

    target: str
    when: str
    max_iterations: int = 5

    @field_validator("max_iterations")
    @classmethod
    def max_iterations_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_iterations must be >= 1")
        return v


class NodeSpec(BaseModel):
    """A single node definition within a workflow."""

    id: str = ""
    agent: str
    system_prompt: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str]
    depends_on: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    retry_policy: RetryPolicy | None = None
    deadline_ms: int | None = None
    when: str | None = None
    tools: list[Any] = Field(default_factory=list)
    cost: NodeCostHint | None = None
    budget: float | NodeBudget | None = None
    back_edge: BackEdge | None = None
    output_schema: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _normalize_budget(self) -> NodeSpec:
        """Convert float/int shorthand to NodeBudget."""
        if isinstance(self.budget, (int, float)):
            self.budget = NodeBudget(max_cost=float(self.budget))
        return self


class DefaultsSpec(BaseModel):
    """Default settings for all nodes in a workflow."""

    deadline_ms: int = 120000
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class WebhookConfig(BaseModel):
    """Webhook notification target configuration."""

    url: str


class WorkflowSpec(BaseModel):
    """Parsed representation of a YAML/JSON workflow definition."""

    version: int = 1
    name: str
    description: str = ""
    nodes: dict[str, NodeSpec]
    defaults: DefaultsSpec | None = None
    budget: BudgetConfig | None = None
    webhook: WebhookConfig | None = None
    source_path: str | None = None

    @field_validator("version")
    @classmethod
    def version_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be >= 1")
        return v

    @model_validator(mode="after")
    def _set_node_ids(self) -> WorkflowSpec:
        for key, node in self.nodes.items():
            if not node.id:
                node.id = key
        return self


__all__ = ["BackEdge", "DefaultsSpec", "NodeSpec", "WebhookConfig", "WorkflowSpec"]
