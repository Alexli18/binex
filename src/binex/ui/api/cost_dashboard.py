"""Cost dashboard API endpoints for Binex Web UI."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from binex.cli import get_stores

router = APIRouter(prefix="/costs", tags=["cost-dashboard"])


def _get_stores():
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

        # Collect cost records for filtered runs
        all_cost_records = []
        for run in runs:
            records = await exec_store.list_costs(run.run_id)
            all_cost_records.extend(records)

        # Aggregate totals
        total_cost = sum(r.cost for r in all_cost_records)
        run_count = len(runs)
        avg_per_run = total_cost / run_count if run_count > 0 else 0.0

        # Group by model
        model_agg: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        for r in all_cost_records:
            key = r.model or "unknown"
            model_agg[key]["cost"] += r.cost
            model_agg[key]["count"] += 1
        cost_by_model = [
            {"model": model, "cost": round(data["cost"], 6), "count": data["count"]}
            for model, data in sorted(model_agg.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]

        # Group by node
        node_agg: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        for r in all_cost_records:
            node_agg[r.task_id]["cost"] += r.cost
            node_agg[r.task_id]["count"] += 1
        cost_by_node = [
            {"node_id": node_id, "cost": round(data["cost"], 6), "count": data["count"]}
            for node_id, data in sorted(node_agg.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]

        # Cost trend — group by date
        date_agg: dict[str, dict] = defaultdict(lambda: {"cost": 0.0, "runs": set()})
        for r in all_cost_records:
            date_key = r.timestamp.strftime("%Y-%m-%d")
            date_agg[date_key]["cost"] += r.cost
            date_agg[date_key]["runs"].add(r.run_id)
        cost_trend = [
            {"date": date, "cost": round(data["cost"], 6), "runs": len(data["runs"])}
            for date, data in sorted(date_agg.items())
        ]

        return JSONResponse({
            "period": period,
            "total_cost": round(total_cost, 6),
            "avg_per_run": round(avg_per_run, 6),
            "run_count": run_count,
            "cost_by_model": cost_by_model,
            "cost_by_node": cost_by_node,
            "cost_trend": cost_trend,
        })
    finally:
        await exec_store.close()
