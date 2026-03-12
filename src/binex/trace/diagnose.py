"""Automated root-cause analysis for failed workflow runs."""

from __future__ import annotations

import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from binex.models.execution import ExecutionRecord
    from binex.stores.backends.filesystem import FilesystemArtifactStore
    from binex.stores.backends.sqlite import SqliteExecutionStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LATENCY_ANOMALY_THRESHOLD = 3.0
MIN_LATENCY_SAMPLES = 2
MS_PER_SECOND = 1000

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RootCause:
    node_id: str
    error_message: str
    pattern: str  # "timeout", "rate_limit", "auth", "budget", "connection", "unknown"


@dataclass
class LatencyAnomaly:
    node_id: str
    latency_ms: float
    median_ms: float
    ratio: float  # always > LATENCY_ANOMALY_THRESHOLD


@dataclass
class DiagnosticReport:
    run_id: str
    status: str  # "issues_found" or "clean"
    root_cause: RootCause | None = None
    affected_nodes: list[str] = field(default_factory=list)
    latency_anomalies: list[LatencyAnomaly] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, list[str]]] = [
    ("timeout", ["timeout", "timed out", "deadline exceeded"]),
    ("rate_limit", ["rate limit", "rate_limit", "429", "too many requests"]),
    ("auth", ["auth", "unauthorized", "403", "forbidden", "api key"]),
    ("budget", ["budget", "exceeded budget", "over_budget"]),
    ("connection", ["connection", "connect", "refused", "unreachable", "dns"]),
]


def classify_error(error_message: str) -> str:
    """Classify an error message into a known pattern category."""
    lower = error_message.lower()
    for pattern_name, keywords in _PATTERNS:
        for kw in keywords:
            if kw in lower:
                return pattern_name
    return "unknown"


# ---------------------------------------------------------------------------
# Root-cause detection
# ---------------------------------------------------------------------------

def find_root_cause(
    records: list[ExecutionRecord],
    dag_order: list[str],
) -> RootCause | None:
    """Find the first failed node in topological (DAG) order."""
    failed_by_task: dict[str, ExecutionRecord] = {
        rec.task_id: rec for rec in records if rec.status.value == "failed"
    }
    if not failed_by_task:
        return None

    for node_id in dag_order:
        if node_id in failed_by_task:
            rec = failed_by_task[node_id]
            return RootCause(
                node_id=rec.task_id,
                error_message=rec.error or "unknown error",
                pattern=classify_error(rec.error or ""),
            )
    # Fallback: first failed record if not in dag_order
    rec = next(iter(failed_by_task.values()))
    return RootCause(
        node_id=rec.task_id,
        error_message=rec.error or "unknown error",
        pattern=classify_error(rec.error or ""),
    )


# ---------------------------------------------------------------------------
# Cascade detection
# ---------------------------------------------------------------------------

def detect_cascade(
    root_node_id: str,
    records: list[ExecutionRecord],
    dag: object | None = None,
) -> list[str]:
    """Collect downstream nodes affected by the root failure.

    If *dag* is provided and has a ``dependents`` method, performs a
    breadth-first walk.  Otherwise falls back to collecting all
    failed / skipped records that are not the root cause.
    """
    status_map: dict[str, str] = {
        rec.task_id: rec.status.value for rec in records
    }

    if dag is not None and hasattr(dag, "dependents"):
        affected: list[str] = []
        visited: set[str] = set()
        queue: deque[str] = deque()
        for dep in dag.dependents(root_node_id):
            queue.append(dep)
        while queue:
            nid = queue.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            st = status_map.get(nid, "")
            if st in ("failed", "skipped"):
                affected.append(nid)
            for child in dag.dependents(nid):
                queue.append(child)
        return affected

    # Fallback: no DAG available
    return [
        rec.task_id
        for rec in records
        if rec.task_id != root_node_id
        and rec.status.value in ("failed", "skipped")
    ]


# ---------------------------------------------------------------------------
# Latency anomaly detection
# ---------------------------------------------------------------------------

def detect_latency_anomalies(
    records: list[ExecutionRecord],
) -> list[LatencyAnomaly]:
    """Flag nodes whose latency exceeds LATENCY_ANOMALY_THRESHOLD x the median."""
    latencies = [rec.latency_ms for rec in records if rec.latency_ms > 0]
    if len(latencies) < MIN_LATENCY_SAMPLES:
        return []

    med = statistics.median(latencies)
    if med <= 0:
        return []

    anomalies: list[LatencyAnomaly] = []
    for rec in records:
        if rec.latency_ms <= 0:
            continue
        ratio = rec.latency_ms / med
        if ratio > LATENCY_ANOMALY_THRESHOLD:
            anomalies.append(LatencyAnomaly(
                node_id=rec.task_id,
                latency_ms=float(rec.latency_ms),
                median_ms=float(med),
                ratio=ratio,
            ))
    return anomalies


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

_ADVICE: dict[str, str] = {
    "timeout": "increasing deadline or investigating slow dependencies",
    "rate_limit": "reducing parallelism or adding backoff",
    "auth": "checking API key and permissions",
    "budget": "increasing budget allocation",
    "connection": "verifying endpoint connectivity",
    "unknown": "reviewing error logs",
}


def generate_recommendations(
    root_cause: RootCause | None,
    anomalies: list[LatencyAnomaly],
) -> list[str]:
    """Produce actionable suggestions based on analysis results."""
    recs: list[str] = []

    if root_cause:
        advice = _ADVICE.get(root_cause.pattern, "reviewing error logs")
        recs.append(
            f"Root cause: node '{root_cause.node_id}' failed with "
            f"{root_cause.pattern} error. Consider {advice}."
        )

    for a in anomalies:
        recs.append(
            f"Node '{a.node_id}' took {a.ratio:.1f}x median latency "
            f"({a.latency_ms / MS_PER_SECOND:.1f}s vs {a.median_ms / MS_PER_SECOND:.1f}s median). "
            f"Consider investigating performance."
        )

    return recs


# ---------------------------------------------------------------------------
# Top-level diagnose function
# ---------------------------------------------------------------------------

async def diagnose_run(
    exec_store: SqliteExecutionStore,
    art_store: FilesystemArtifactStore,
    run_id: str,
) -> DiagnosticReport:
    """Run full diagnostic analysis on a workflow run."""
    run = await exec_store.get_run(run_id)
    if run is None:
        msg = f"Run '{run_id}' not found"
        raise ValueError(msg)

    records = await exec_store.list_records(run_id)

    # Check if there are any failures or skipped nodes
    has_failures = any(
        rec.status.value in ("failed", "skipped") for rec in records
    )
    if not has_failures:
        return DiagnosticReport(run_id=run_id, status="clean")

    # Build topological order from record ordering (first to last)
    dag_order = [rec.task_id for rec in records]

    root_cause = find_root_cause(records, dag_order)
    affected: list[str] = []
    if root_cause:
        affected = detect_cascade(root_cause.node_id, records)

    anomalies = detect_latency_anomalies(records)
    recommendations = generate_recommendations(root_cause, anomalies)

    return DiagnosticReport(
        run_id=run_id,
        status="issues_found",
        root_cause=root_cause,
        affected_nodes=affected,
        latency_anomalies=anomalies,
        recommendations=recommendations,
    )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def report_to_dict(report: DiagnosticReport) -> dict:
    """Convert a *DiagnosticReport* to a JSON-serialisable dict."""
    return {
        "run_id": report.run_id,
        "status": report.status,
        "root_cause": (
            {
                "node_id": report.root_cause.node_id,
                "error_message": report.root_cause.error_message,
                "pattern": report.root_cause.pattern,
            }
            if report.root_cause
            else None
        ),
        "affected_nodes": report.affected_nodes,
        "latency_anomalies": [
            {
                "node_id": a.node_id,
                "latency_ms": a.latency_ms,
                "median_ms": a.median_ms,
                "ratio": a.ratio,
            }
            for a in report.latency_anomalies
        ],
        "recommendations": report.recommendations,
    }
