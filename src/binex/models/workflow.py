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


class McpServerConfig(BaseModel):
    """MCP server configuration — stdio or HTTP/SSE transport."""

    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None

    @model_validator(mode="after")
    def _must_have_transport(self) -> McpServerConfig:
        if not self.command and not self.url:
            raise ValueError(
                "MCP server must have either 'command' (stdio) or 'url' (HTTP/SSE)"
            )
        if self.command and self.url:
            raise ValueError(
                "MCP server must have either 'command' OR 'url', not both"
            )
        return self


_LOOP_EXIT_OPERATORS = {">=", "<=", ">", "<", "==", "!="}


class LoopExitCondition(BaseModel):
    """Exit condition for a loop container — evaluated after each iteration."""

    field: str
    operator: str
    value: float | str | bool

    @field_validator("operator")
    @classmethod
    def _valid_operator(cls, v: str) -> str:
        if v not in _LOOP_EXIT_OPERATORS:
            raise ValueError(
                f"operator must be one of {sorted(_LOOP_EXIT_OPERATORS)}, got {v!r}"
            )
        return v

    @field_validator("field")
    @classmethod
    def _valid_jsonpath(cls, v: str) -> str:
        if not v.startswith("$."):
            raise ValueError(
                f"field must be a JSONPath starting with '$.' , got {v!r}"
            )
        return v


class LoopSpec(BaseModel):
    """Loop container specification — iterative execution of child nodes."""

    exit: LoopExitCondition
    max_iterations: int = 5
    timeout_minutes: float | None = None
    accumulate: bool = False
    contains: list[str]

    @field_validator("max_iterations")
    @classmethod
    def _max_iterations_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_iterations must be >= 1")
        return v

    @field_validator("timeout_minutes")
    @classmethod
    def _timeout_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("timeout_minutes must be > 0")
        return v

    @field_validator("contains")
    @classmethod
    def _contains_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("contains must have at least one node")
        return v


class NodeSpec(BaseModel):
    """A single node definition within a workflow."""

    id: str = ""
    type: str | None = None
    agent: str = ""
    system_prompt: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)
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
    loop: LoopSpec | None = None

    @model_validator(mode="after")
    def _normalize_budget(self) -> NodeSpec:
        """Convert float/int shorthand to NodeBudget."""
        if isinstance(self.budget, (int, float)):
            self.budget = NodeBudget(max_cost=float(self.budget))
        return self

    @model_validator(mode="after")
    def _validate_loop_fields(self) -> NodeSpec:
        """Validate loop-specific field constraints."""
        if self.type == "loop":
            if self.loop is None:
                raise ValueError(
                    "Node with type='loop' must have a 'loop' specification"
                )
            if not self.agent:
                self.agent = "loop://container"
        else:
            if self.loop is not None:
                raise ValueError(
                    "Node with loop specification must have type='loop'"
                )
            if not self.agent:
                raise ValueError(
                    "Non-loop nodes must have an 'agent' field"
                )
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
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
    schedule: str | None = None
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


__all__ = [
    "BackEdge",
    "DefaultsSpec",
    "LoopExitCondition",
    "LoopSpec",
    "McpServerConfig",
    "NodeSpec",
    "WebhookConfig",
    "WorkflowSpec",
]
