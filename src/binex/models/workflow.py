"""WorkflowSpec, NodeSpec, and DefaultsSpec domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from binex.models.task import RetryPolicy


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


class DefaultsSpec(BaseModel):
    """Default settings for all nodes in a workflow."""

    deadline_ms: int = 120000
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class WorkflowSpec(BaseModel):
    """Parsed representation of a YAML/JSON workflow definition."""

    name: str
    description: str = ""
    nodes: dict[str, NodeSpec]
    defaults: DefaultsSpec | None = None

    @model_validator(mode="after")
    def _set_node_ids(self) -> WorkflowSpec:
        for key, node in self.nodes.items():
            if not node.id:
                node.id = key
        return self


__all__ = ["DefaultsSpec", "NodeSpec", "WorkflowSpec"]
