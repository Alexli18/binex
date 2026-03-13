"""Export serializers — CSV and JSON writers for run data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from binex.models.artifact import Artifact
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary

_RUN_FIELDS = [
    "run_id", "workflow_name", "workflow_path", "status",
    "started_at", "completed_at", "total_nodes", "completed_nodes",
    "failed_nodes", "skipped_nodes", "total_cost",
]

_RECORD_FIELDS = [
    "id", "run_id", "task_id", "agent_id", "status", "latency_ms",
    "timestamp", "trace_id", "error", "prompt", "model", "tool_calls",
]

_COST_FIELDS = [
    "id", "run_id", "task_id", "cost", "currency", "source",
    "prompt_tokens", "completion_tokens", "model", "timestamp",
]


def write_runs_csv(runs: list[RunSummary], path: Path) -> None:
    """Write run summaries to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_RUN_FIELDS)
        writer.writeheader()
        for run in runs:
            row = run.model_dump()
            writer.writerow({k: row.get(k, "") for k in _RUN_FIELDS})


def write_records_csv(records: list[ExecutionRecord], path: Path) -> None:
    """Write execution records to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_RECORD_FIELDS)
        writer.writeheader()
        for record in records:
            row = record.model_dump()
            writer.writerow({k: row.get(k, "") for k in _RECORD_FIELDS})


def write_costs_csv(costs: list[CostRecord], path: Path) -> None:
    """Write cost records to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_COST_FIELDS)
        writer.writeheader()
        for cost in costs:
            row = cost.model_dump()
            writer.writerow({k: row.get(k, "") for k in _COST_FIELDS})


def write_json(
    *,
    runs: list[RunSummary],
    records: list[ExecutionRecord],
    costs: list[CostRecord],
    path: Path,
    artifacts: list[Artifact] | None = None,
) -> None:
    """Write all data to a single JSON file."""
    data: dict = {
        "runs": [r.model_dump() for r in runs],
        "records": [r.model_dump() for r in records],
        "costs": [c.model_dump() for c in costs],
    }
    if artifacts is not None:
        data["artifacts"] = [a.model_dump() for a in artifacts]
    with open(path, "w") as f:
        json.dump(data, f, default=str, indent=2)
