"""ExecutionStore protocol — interface for execution record persistence."""

from __future__ import annotations

from typing import Any, Protocol

from binex.models.cache import CacheEntry
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

    async def list_runs(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[RunSummary]:
        """List run summaries with optional pagination.

        Args:
            limit: Maximum number of runs to return. ``None`` means no limit.
            offset: Number of runs to skip (default ``0``).
        """
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

    async def list_costs_batch(self, run_ids: list[str]) -> list[CostRecord]:
        """Fetch cost records for multiple run_ids in a single query."""
        ...

    async def get_cost_aggregations(
        self, run_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Return SQL-aggregated cost breakdowns by model, node, and date."""
        ...

    async def get_node_cost(self, run_id: str, task_id: str) -> float:
        """Get the total cost for a specific node in a run."""
        ...

    async def get_run_cost_summary(self, run_id: str) -> RunCostSummary:
        """Get aggregated cost summary for a run."""
        ...

    # ------------------------------------------------------------------
    # CAO session registry
    # ------------------------------------------------------------------

    async def create_cao_session(
        self, terminal_id: str, run_id: str, node_name: str,
        session_name: str | None = None,
    ) -> None:
        """Persist an active CAO session."""
        ...

    async def complete_cao_session(self, terminal_id: str) -> None:
        """Mark session as completed."""
        ...

    async def get_cao_sessions(
        self, status: str | None = None,
    ) -> list[dict[str, str]]:
        """List CAO sessions, optionally filtered by status."""
        ...

    async def get_orphaned_cao_sessions(self) -> list[dict[str, str]]:
        """Return sessions with status 'orphaned'."""
        ...

    async def mark_cao_sessions_orphaned(self, terminal_ids: list[str]) -> None:
        """Mark active sessions as orphaned (crash recovery)."""
        ...

    async def delete_cao_session(self, terminal_id: str) -> bool:
        """Delete a session by terminal_id."""
        ...

    # ------------------------------------------------------------------
    # Workflow snapshots
    # ------------------------------------------------------------------

    async def store_workflow_snapshot(self, content: str, version: int) -> str:
        """Store workflow YAML content, deduplicated by hash. Returns hash."""
        ...

    async def get_workflow_snapshot(self, content_hash: str) -> dict[str, Any] | None:
        """Retrieve a workflow snapshot by hash."""
        ...

    # ------------------------------------------------------------------
    # Node cache
    # ------------------------------------------------------------------

    async def get_cache_entry(self, cache_key: str) -> CacheEntry | None:
        """Retrieve a cached node result by key, or None on miss."""
        ...

    async def put_cache_entry(self, entry: CacheEntry) -> None:
        """Store (or overwrite) a cached node result."""
        ...

    async def count_cache_entries(self) -> int:
        """Return the number of cache entries."""
        ...

    async def clear_cache_entries(self, older_than_days: float | None = None) -> int:
        """Delete cache entries (all, or older than N days). Returns count deleted."""
        ...

    # ------------------------------------------------------------------
    # Eval baselines and results
    # ------------------------------------------------------------------

    async def set_baseline(
        self, suite_name: str, case_id: str, run_id: str,
    ) -> None:
        """Upsert the blessed baseline run_id for a (suite_name, case_id) pair."""
        ...

    async def get_baselines(self, suite_name: str) -> dict[str, str]:
        """Return {case_id: run_id} mapping for all baselines in a suite."""
        ...

    async def save_eval_result(self, result: Any) -> str:
        """Persist an EvalResult; returns its generated id."""
        ...

    async def list_eval_results(
        self, limit: int = 50, suite_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent eval results (summary dicts), newest first."""
        ...

    async def get_eval_result(self, result_id: str) -> dict[str, Any] | None:
        """Retrieve a single eval result payload by id."""
        ...


__all__ = ["ExecutionStore"]
