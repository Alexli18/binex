"""CLI `binex eval` — run a workflow as a regression check (issue #60).

Exits non-zero when the run fails (including a failed assertion) or, with
``--baseline``, when the run diverges from a golden run beyond thresholds.
Designed to drop into CI on PRs that touch workflow YAML or prompts.
"""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli.run import _parse_vars


@click.command("eval", epilog="""\b
Examples:
  binex eval workflow.yaml                          Run + enforce node assertions
  binex eval workflow.yaml --baseline run_abc123     Compare against a golden run
  binex eval workflow.yaml --baseline run_abc123 \\
      --min-similarity 0.9 --max-cost-delta 0.01     Loosen regression thresholds
""")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--var", multiple=True, help="Variable substitution key=value")
@click.option("--baseline", default=None,
              help="Run ID of a golden run to diff against")
@click.option("--min-similarity", type=float, default=1.0, show_default=True,
              help="Content similarity floor vs baseline (1.0 = must be identical)")
@click.option("--max-latency-delta-ms", type=float, default=None,
              help="Fail if total latency grows by more than this (ms)")
@click.option("--max-cost-delta", type=float, default=None,
              help="Fail if total cost grows by more than this")
@click.option("--gateway", "gateway_url", default=None,
              help="A2A Gateway URL for routing a2a:// agents")
@click.option("--json-output", "--json", "json_out", is_flag=True,
              help="Output the report as JSON")
def eval_cmd(
    workflow_file: str,
    var: tuple[str, ...],
    baseline: str | None,
    min_similarity: float,
    max_latency_delta_ms: float | None,
    max_cost_delta: float | None,
    gateway_url: str | None,
    json_out: bool,
) -> None:
    """Run a workflow and gate on assertions and/or a baseline diff."""
    from binex.eval.runner import EvalError, EvalThresholds, run_eval

    user_vars = _parse_vars(var)
    thresholds = EvalThresholds(
        min_similarity=min_similarity,
        max_latency_delta_ms=max_latency_delta_ms,
        max_cost_delta=max_cost_delta,
    )

    try:
        report = asyncio.run(run_eval(
            workflow_file,
            user_vars=user_vars,
            baseline=baseline,
            thresholds=thresholds,
            gateway_url=gateway_url,
        ))
    except EvalError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if json_out:
        click.echo(json.dumps({
            "run_id": report.run_id,
            "run_status": report.run_status,
            "baseline_run_id": report.baseline_run_id,
            "node_errors": [
                {"node": nid, "error": err} for nid, err in report.node_errors
            ],
            "divergences": report.divergences,
            "passed": report.passed,
        }, indent=2))
    else:
        _print_report(report)

    sys.exit(0 if report.passed else 1)


def _print_report(report: object) -> None:
    """Render a human-readable eval report to stderr/stdout."""
    r = report  # typed loosely to avoid importing the dataclass here
    click.echo(f"Run: {r.run_id}  ({r.run_status})")  # type: ignore[attr-defined]

    for node_id, err in r.node_errors:  # type: ignore[attr-defined]
        click.echo(f"  [{node_id}] {err}", err=True)

    if r.baseline_run_id:  # type: ignore[attr-defined]
        click.echo(f"Baseline: {r.baseline_run_id}")  # type: ignore[attr-defined]
        if r.divergences:  # type: ignore[attr-defined]
            click.echo("Divergences:", err=True)
            for d in r.divergences:  # type: ignore[attr-defined]
                click.echo(f"  - {d}", err=True)
        else:
            click.echo("No divergence beyond thresholds.")

    if r.passed:  # type: ignore[attr-defined]
        click.echo("PASS")
    else:
        click.echo("FAIL", err=True)
