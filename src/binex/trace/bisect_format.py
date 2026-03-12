"""Bisect report serialization — convert dataclasses to dicts."""
from __future__ import annotations

from typing import Any

from binex.trace.bisect import BisectReport, DivergencePoint


def divergence_to_dict(
    good_run_id: str,
    bad_run_id: str,
    divergence: DivergencePoint | None,
) -> dict[str, Any]:
    """Convert bisect result to JSON-serializable dict."""
    result: dict[str, Any] = {
        "good_run_id": good_run_id,
        "bad_run_id": bad_run_id,
    }
    if divergence is None:
        result["divergence"] = None
        result["message"] = "No divergence found"
    else:
        result["divergence"] = {
            "node_id": divergence.node_id,
            "divergence_type": divergence.divergence_type,
            "similarity": divergence.similarity,
            "good_status": divergence.good_status,
            "bad_status": divergence.bad_status,
            "upstream_context": divergence.upstream_context,
        }
    return result


def bisect_report_to_dict(report: BisectReport) -> dict[str, Any]:
    """Convert a BisectReport to a JSON-serializable dict."""
    result: dict[str, Any] = {
        "good_run_id": report.good_run_id,
        "bad_run_id": report.bad_run_id,
        "workflow_name": report.workflow_name,
    }

    if report.divergence_point is None:
        result["divergence"] = None
        result["message"] = "No divergence found"
    else:
        dp = report.divergence_point
        result["divergence"] = {
            "node_id": dp.node_id,
            "divergence_type": dp.divergence_type,
            "similarity": dp.similarity,
            "good_status": dp.good_status,
            "bad_status": dp.bad_status,
            "upstream_context": dp.upstream_context,
        }

    result["node_map"] = [
        {
            "node_id": nc.node_id,
            "status": nc.status,
            "good_status": nc.good_status,
            "bad_status": nc.bad_status,
            "similarity": nc.similarity,
            "latency_good_ms": nc.latency_good_ms,
            "latency_bad_ms": nc.latency_bad_ms,
            "content_diff": nc.content_diff,
        }
        for nc in report.node_map
    ]

    result["error_context"] = (
        {
            "node_id": report.error_context.node_id,
            "error_message": report.error_context.error_message,
            "pattern": report.error_context.pattern,
        }
        if report.error_context
        else None
    )

    result["downstream_impact"] = report.downstream_impact

    return result
