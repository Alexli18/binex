"""ExecutionRecord and RunSummary domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from binex.models.task import TaskStatus


class ExecutionRecord(BaseModel):
    """Metadata about a single node execution."""

    id: str
    run_id: str
    task_id: str
    parent_task_id: str | None = None
    agent_id: str
    status: TaskStatus
    input_artifact_refs: list[str] = Field(default_factory=list)
    output_artifact_refs: list[str] = Field(default_factory=list)
    prompt: str | None = None
    model: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    latency_ms: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str
    error: str | None = None


class RunSummary(BaseModel):
    """Summary of a complete workflow run."""

    run_id: str
    workflow_name: str
    workflow_path: str | None = None
    status: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    total_nodes: int
    completed_nodes: int = 0
    failed_nodes: int = 0
    skipped_nodes: int = 0
    forked_from: str | None = None
    forked_at_step: str | None = None
    total_cost: float = 0.0


__all__ = ["ExecutionRecord", "RunSummary"]
