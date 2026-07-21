"""`binex eval` runner — run a workflow and gate on assertions + baseline diff.

Combines two regression signals into one pass/fail verdict:

* the run's own status (a failed node — including one that failed an assertion —
  fails the eval), and
* a diff against a stored "golden" run, where divergence beyond configured
  thresholds fails the eval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class EvalError(Exception):
    """Raised for setup problems (invalid workflow, missing baseline run)."""


@dataclass
class EvalThresholds:
    """Tolerances for a baseline comparison. Defaults gate on any regression."""

    min_similarity: float = 1.0
    max_latency_delta_ms: float | None = None
    max_cost_delta: float | None = None


@dataclass
class EvalReport:
    """Outcome of an eval run."""

    run_id: str
    run_status: str
    node_errors: list[tuple[str, str]] = field(default_factory=list)
    baseline_run_id: str | None = None
    diff: dict[str, Any] | None = None
    divergences: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.run_status == "completed" and not self.divergences


def check_divergences(
    diff: dict[str, Any], thresholds: EvalThresholds,
) -> list[str]:
    """List the ways a diff exceeds the thresholds (empty = within tolerance)."""
    out: list[str] = []
    summary = diff["summary"]

    similarity = summary.get("content_similarity", 1.0)
    if similarity < thresholds.min_similarity:
        out.append(
            f"content similarity {similarity:.4g} < min {thresholds.min_similarity:.4g}"
        )

    latency_delta = summary.get("latency_delta_ms", 0.0)
    if (
        thresholds.max_latency_delta_ms is not None
        and latency_delta > thresholds.max_latency_delta_ms
    ):
        out.append(
            f"latency delta {latency_delta:.0f}ms > max "
            f"{thresholds.max_latency_delta_ms:.0f}ms"
        )

    cost_delta = summary.get("cost_delta", 0.0)
    if (
        thresholds.max_cost_delta is not None
        and cost_delta > thresholds.max_cost_delta
    ):
        out.append(
            f"cost delta {cost_delta:.6g} > max {thresholds.max_cost_delta:.6g}"
        )

    for step in diff["steps"]:
        if step["status_changed"]:
            out.append(
                f"node '{step['task_id']}' status "
                f"{step['status_a']} -> {step['status_b']}"
            )

    return out


async def run_eval(
    workflow_file: str,
    *,
    user_vars: dict[str, str] | None = None,
    baseline: str | None = None,
    thresholds: EvalThresholds | None = None,
    gateway_url: str | None = None,
) -> EvalReport:
    """Run a workflow and produce an :class:`EvalReport`."""
    from binex.cli import get_stores
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.orchestrator import Orchestrator
    from binex.trace.diff import diff_runs
    from binex.workflow_spec.loader import load_workflow
    from binex.workflow_spec.validator import validate_workflow

    thresholds = thresholds or EvalThresholds()
    spec = load_workflow(workflow_file, user_vars=user_vars or {})

    validation_errors = validate_workflow(spec)
    if validation_errors:
        raise EvalError("; ".join(validation_errors))

    exec_store, art_store = get_stores()
    try:
        if baseline is not None and await exec_store.get_run(baseline) is None:
            raise EvalError(f"baseline run '{baseline}' not found")

        orch = Orchestrator(artifact_store=art_store, execution_store=exec_store)
        registry = PluginRegistry()
        registry.discover()
        register_workflow_adapters(
            orch.dispatcher, spec, gateway_url=gateway_url,
            plugin_registry=registry,
        )

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)
        node_errors = [(r.task_id, r.error) for r in records if r.error]

        diff: dict[str, Any] | None = None
        divergences: list[str] = []
        if baseline is not None:
            diff = await diff_runs(exec_store, art_store, baseline, summary.run_id)
            divergences = check_divergences(diff, thresholds)

        return EvalReport(
            run_id=summary.run_id,
            run_status=summary.status,
            node_errors=node_errors,
            baseline_run_id=baseline,
            diff=diff,
            divergences=divergences,
        )
    finally:
        await exec_store.close()


__all__ = [
    "EvalError",
    "EvalReport",
    "EvalThresholds",
    "check_divergences",
    "run_eval",
]
