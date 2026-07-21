"""WorkflowSpec, NodeSpec, and DefaultsSpec domain models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from binex.models.assertion import Assertion
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


class CaoConfig(BaseModel):
    """Per-node CAO configuration — embedded in NodeSpec as optional field."""

    mode: Literal["handoff"] = "handoff"
    provider: Literal["claude_code", "kiro_cli", "q_cli"] | None = None
    output_format: Literal["auto", "json", "text"] = "auto"
    output_field: str | None = None
    timeout_minutes: int = 60
    max_human_prompts: int = 10
    completion_marker: bool = False
    min_wait_seconds: int = 0
    quiescence_seconds: int = 30

    @model_validator(mode="after")
    def _validate_cao_config(self) -> CaoConfig:
        if self.output_field and self.output_format != "json":
            raise ValueError("output_field requires output_format='json'")
        if self.output_field and not self.output_field.startswith("$."):
            raise ValueError("output_field must be a JSONPath starting with '$.'")
        if self.timeout_minutes < 1:
            raise ValueError("timeout_minutes must be >= 1")
        if self.max_human_prompts < 1:
            raise ValueError("max_human_prompts must be >= 1")
        return self


class RepairConfig(BaseModel):
    """Auto-repair settings for a node with an ``output_schema``.

    Deterministic repair (strip code fences, extract balanced JSON) is always on
    for schema-validated nodes; ``max_attempts`` controls the LLM feedback loop.
    """

    max_attempts: int = 0  # feedback-loop attempts (LLM nodes only)
    escalate: bool = False  # promote to next fallback model on exhaustion (see #67)

    @field_validator("max_attempts")
    @classmethod
    def _non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("repair.max_attempts must be >= 0")
        return v


class NodeSpec(BaseModel):
    """A single node definition within a workflow."""

    id: str = ""
    agent: str
    pattern: str | None = None
    system_prompt: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: list[str]
    depends_on: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    retry_policy: RetryPolicy | None = None
    deadline_ms: int | None = None
    heartbeat_timeout_ms: int | None = None
    when: str | None = None
    tools: list[Any] = Field(default_factory=list)
    cost: NodeCostHint | None = None
    budget: float | NodeBudget | None = None
    back_edge: BackEdge | None = None
    output_schema: dict[str, Any] | None = None
    cache: bool = False
    repair: RepairConfig | None = None
    fallbacks: list[str] = Field(default_factory=list)
    routing: dict[str, Any] | None = None
    cao: CaoConfig | None = None
    assertions: list[Assertion] = Field(default_factory=list)

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
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)
    schedule: str | None = None
    concurrency: int | dict[str, int] | None = None
    source_path: str | None = None

    @field_validator("version")
    @classmethod
    def version_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("version must be >= 1")
        return v

    @field_validator("concurrency")
    @classmethod
    def concurrency_must_be_positive(
        cls, v: int | dict[str, int] | None,
    ) -> int | dict[str, int] | None:
        if v is None:
            return v
        values = [v] if isinstance(v, int) else list(v.values())
        if any(n < 1 for n in values):
            raise ValueError("concurrency limits must be >= 1")
        return v

    @model_validator(mode="after")
    def _set_node_ids(self) -> WorkflowSpec:
        for key, node in self.nodes.items():
            if not node.id:
                node.id = key
        return self


__all__ = [
    "Assertion",
    "BackEdge",
    "CaoConfig",
    "DefaultsSpec",
    "McpServerConfig",
    "NodeSpec",
    "RepairConfig",
    "WebhookConfig",
    "WorkflowSpec",
]
