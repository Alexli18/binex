"""ExecutionStore protocol — interface for execution record persistence."""

from __future__ import annotations

from typing import Protocol

from binex.models.cost import CostRecord, RunCostSummary
from binex.models.execution import ExecutionRecord, RunSummary


class ExecutionStore(Protocol):
    """Protocol for storing and retrieving execution records and run summaries."""

    async def record(self, execution_record: ExecutionRecord) -> None:
        """Persist an execution record."""
        ...

    async def get_run(self, run_id: str) -> RunSummary | None:
        """Retrieve a run summary by run ID."""
        ...

    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None:
        """Retrieve a specific execution record for a run/task pair."""
        ...

    async def list_runs(self) -> list[RunSummary]:
        """List all run summaries."""
        ...

    async def create_run(self, run_summary: RunSummary) -> None:
        """Create a new run summary."""
        ...

    async def update_run(self, run_summary: RunSummary) -> None:
        """Update an existing run summary."""
        ...

    async def list_records(self, run_id: str) -> list[ExecutionRecord]:
        """List all execution records for a given run."""
        ...

    async def record_cost(self, cost_record: CostRecord) -> None:
        """Persist a cost record."""
        ...

    async def list_costs(self, run_id: str) -> list[CostRecord]:
        """List all cost records for a given run."""
        ...

    async def get_run_cost_summary(self, run_id: str) -> RunCostSummary:
        """Get aggregated cost summary for a run."""
        ...


__all__ = ["ExecutionStore"]
