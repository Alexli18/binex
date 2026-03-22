"""Cost dashboard API endpoints for Binex Web UI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from binex.cli import get_stores
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore

router = APIRouter(prefix="/costs", tags=["cost-dashboard"])


def _get_stores() -> tuple[
    InMemoryExecutionStore | SqliteExecutionStore,
    InMemoryArtifactStore | FilesystemArtifactStore,
]:
    """Create default stores. Extracted for test patching."""
    return get_stores()


_PERIOD_DELTAS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@router.get("/dashboard")
async def cost_dashboard(
    period: str = Query("7d", pattern="^(24h|7d|30d|all)$"),
) -> JSONResponse:
    """Aggregate cost dashboard across all runs for a time period."""
    exec_store, _ = _get_stores()
    try:
        runs = await exec_store.list_runs()

        # Filter runs by period
        now = datetime.now(UTC)
        if period != "all":
            delta = _PERIOD_DELTAS[period]
            cutoff = now - delta
            runs = [r for r in runs if r.started_at >= cutoff]

        run_ids = [r.run_id for r in runs]
        run_count = len(runs)

        # Batch-fetch costs and aggregate at SQL level (avoids N+1 and in-memory aggregation)
        aggs = await exec_store.get_cost_aggregations(run_ids)
        total_cost = sum(m["cost"] for m in aggs["by_model"])
        avg_per_run = total_cost / run_count if run_count > 0 else 0.0

        return JSONResponse({
            "period": period,
            "total_cost": round(total_cost, 6),
            "avg_per_run": round(avg_per_run, 6),
            "run_count": run_count,
            "cost_by_model": aggs["by_model"],
            "cost_by_node": aggs["by_node"],
            "cost_trend": aggs["by_date"],
        })
    finally:
        await exec_store.close()
