"""Trace API endpoint for Binex Web UI."""

from __future__ import annotations

import statistics

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from binex.cli import get_stores

router = APIRouter(prefix="/runs", tags=["trace"])

ANOMALY_THRESHOLD = 2.0


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@router.get("/{run_id}/trace")
async def get_trace(run_id: str) -> JSONResponse:
    """Execution trace with timeline and anomaly detection."""
    exec_store, _ = _get_stores()
    try:
        run = await exec_store.get_run(run_id)
        if run is None:
            return JSONResponse(
                {"error": f"Run '{run_id}' not found"}, status_code=404,
            )

        records = await exec_store.list_records(run_id)
        records.sort(key=lambda r: r.timestamp)

        # Compute total duration from run summary
        total_duration_s = 0.0
        if run.started_at and run.completed_at:
            total_duration_s = round(
                (run.completed_at - run.started_at).total_seconds(), 3,
            )

        # Build timeline with offsets
        # rec.timestamp is when the record was created (end time),
        # so start_offset = (timestamp - started_at) - duration
        timeline = []
        for rec in records:
            duration_s = rec.latency_ms / 1000.0 if rec.latency_ms else 0.0
            offset_s = 0.0
            if run.started_at and rec.timestamp:
                end_offset = (rec.timestamp - run.started_at).total_seconds()
                offset_s = round(max(end_offset - duration_s, 0), 3)

            status_str = rec.status.value if hasattr(rec.status, "value") else str(rec.status)
            timeline.append({
                "node_id": rec.task_id,
                "status": status_str,
                "started_at": rec.timestamp.isoformat() if rec.timestamp else None,
                "completed_at": None,
                "duration_s": round(duration_s, 3),
                "offset_s": offset_s,
                "error": rec.error,
            })

        # Detect anomalies: nodes with duration > 2x median
        durations = [rec.latency_ms for rec in records if rec.latency_ms > 0]
        anomalies = []
        if len(durations) >= 2:
            median_ms = statistics.median(durations)
            if median_ms > 0:
                for rec in records:
                    if rec.latency_ms <= 0:
                        continue
                    ratio = rec.latency_ms / median_ms
                    if ratio > ANOMALY_THRESHOLD:
                        anomalies.append({
                            "node_id": rec.task_id,
                            "duration_s": round(rec.latency_ms / 1000.0, 3),
                            "ratio": round(ratio, 1),
                        })

        return JSONResponse({
            "run_id": run.run_id,
            "status": run.status,
            "total_duration_s": total_duration_s,
            "timeline": timeline,
            "anomalies": anomalies,
        })
    finally:
        await exec_store.close()
