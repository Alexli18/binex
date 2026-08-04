"""CLI group: binex eval run|bless|baselines."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import click

from binex.cli import get_stores
from binex.eval.loader import load_suite
from binex.eval.models import EvalResult
from binex.eval.runner import run_suite


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.group("eval")
def eval_group() -> None:
    """Eval suites — run regression tests against blessed baselines."""


# ---------------------------------------------------------------------------
# binex eval run
# ---------------------------------------------------------------------------

@eval_group.command("run")
@click.argument("suite", type=click.Path(exists=False))
@click.option("--parallel", default=1, show_default=True,
              help="Number of cases to run in parallel")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["default", "github"], case_sensitive=False),
    default="default",
    help="Output format (default|github)",
)
@click.option("--strict-baseline", is_flag=True, help="Exit 1 if any case has no baseline")
def eval_run(
    suite: str,
    parallel: int,
    json_out: bool,
    output_format: str,
    strict_baseline: bool,
) -> None:
    """Run all cases in SUITE and compare against blessed baselines."""
    suite_path = Path(suite)

    # Load and validate suite — errors → exit 2
    try:
        eval_suite = load_suite(suite_path)
    except FileNotFoundError:
        click.echo(f"Error: Suite file not found: {suite}", err=True)
        sys.exit(2)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    exec_store, art_store = _get_stores()
    try:
        result = asyncio.run(_run_async(eval_suite, parallel, exec_store, art_store))
    finally:
        asyncio.run(exec_store.close())

    if json_out:
        click.echo(result.model_dump_json(indent=2))
        _exit_from_result(result, strict_baseline)
        return

    _print_table(result)

    if output_format == "github":
        _print_github_annotations(result, suite_path)

    _exit_from_result(result, strict_baseline)


async def _run_async(
    eval_suite: Any,
    parallel: int,
    exec_store: Any,
    art_store: Any,
) -> EvalResult:
    return await run_suite(
        eval_suite, parallel=parallel, exec_store=exec_store, art_store=art_store
    )


def _exit_from_result(result: EvalResult, strict_baseline: bool) -> None:
    has_fail = result.failed > 0
    has_no_baseline = result.no_baseline > 0
    if has_fail or (strict_baseline and has_no_baseline):
        sys.exit(1)


def _print_table(result: EvalResult) -> None:
    click.echo(f"\nEval suite: {result.suite_name}")
    click.echo(
        f"  Total: {result.total}  Pass: {result.passed}  "
        f"Fail: {result.failed}  No baseline: {result.no_baseline}"
    )
    click.echo()
    col_w = [20, 12, 12, 12, 12, 20]
    header = (
        f"{'Case':<{col_w[0]}} {'Verdict':<{col_w[1]}} "
        f"{'Similarity':<{col_w[2]}} {'Cost Δ':<{col_w[3]}} "
        f"{'Latency Δms':<{col_w[4]}} Failed asserts"
    )
    click.echo(header)
    click.echo("-" * sum(col_w))
    for case_result in result.cases:
        sim = f"{case_result.similarity:.3f}" if case_result.similarity is not None else "-"
        cost = f"{case_result.cost_delta:.4f}" if case_result.cost_delta is not None else "-"
        lat = (
            str(case_result.latency_delta_ms)
            if case_result.latency_delta_ms is not None
            else "-"
        )
        failed = len(
            [a for a in case_result.assert_results if a.status in ("failed", "error")]
        )
        row = (
            f"{case_result.case_id:<{col_w[0]}} "
            f"{case_result.verdict:<{col_w[1]}} "
            f"{sim:<{col_w[2]}} "
            f"{cost:<{col_w[3]}} "
            f"{lat:<{col_w[4]}} "
            f"{failed}"
        )
        click.echo(row)
    click.echo()


def _print_github_annotations(result: EvalResult, suite_path: Path) -> None:
    for case_result in result.cases:
        if case_result.verdict == "fail":
            reasons = case_result.violated_thresholds or [case_result.error or "assertion failed"]
            reason_str = "; ".join(str(r) for r in reasons)
            click.echo(f"::error file={suite_path},title={case_result.case_id}::{reason_str}")
        elif case_result.verdict == "no_baseline":
            click.echo(
                f"::warning file={suite_path},title={case_result.case_id}"
                f"::No baseline set — run `binex eval bless` to bless this case"
            )


# ---------------------------------------------------------------------------
# binex eval bless
# ---------------------------------------------------------------------------

@eval_group.command("bless")
@click.argument("suite", type=click.Path(exists=False))
@click.option("--case", "case_id", default=None, help="Bless only this case id")
@click.option("--run", "run_id", default=None, help="Bless a specific run id")
@click.option("--force", is_flag=True, help="Allow blessing a run not tagged to this suite+case")
def eval_bless(suite: str, case_id: str | None, run_id: str | None, force: bool) -> None:
    """Bless latest runs as baselines for SUITE."""
    suite_path = Path(suite)
    try:
        eval_suite = load_suite(suite_path)
    except FileNotFoundError:
        click.echo(f"Error: Suite file not found: {suite}", err=True)
        sys.exit(2)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    exec_store, art_store = _get_stores()
    try:
        asyncio.run(_bless_async(eval_suite, case_id, run_id, force, exec_store))
    finally:
        asyncio.run(exec_store.close())


async def _bless_async(
    eval_suite: Any,
    case_id: str | None,
    run_id: str | None,
    force: bool,
    exec_store: Any,
) -> None:
    # Get runs tagged to this suite
    all_runs = await exec_store.list_runs(limit=500)
    suite_runs = [
        r for r in all_runs
        if r.eval_suite_id == eval_suite.name
    ]

    target_cases = [c for c in eval_suite.cases if case_id is None or c.id == case_id]

    for case in target_cases:
        case_runs = [r for r in suite_runs if r.eval_case_id == case.id]

        if run_id:
            # Find the specific run
            match = next((r for r in case_runs if r.run_id == run_id), None)
            if match is None and not force:
                click.echo(
                    f"Error: Run '{run_id}' is not tagged with suite='{eval_suite.name}' "
                    f"case='{case.id}'. Use --force to override.",
                    err=True,
                )
                sys.exit(2)
            chosen_run_id = run_id
        else:
            if not case_runs:
                click.echo(f"  {case.id}: no tagged runs found, skipping")
                continue
            # Latest run = last in list (creation order)
            chosen_run_id = case_runs[-1].run_id

        await exec_store.set_baseline(eval_suite.name, case.id, chosen_run_id)
        click.echo(f"  Blessed {case.id} → {chosen_run_id}")


# ---------------------------------------------------------------------------
# binex eval baselines
# ---------------------------------------------------------------------------

@eval_group.command("baselines")
@click.argument("suite", type=click.Path(exists=False))
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def eval_baselines(suite: str, json_out: bool) -> None:
    """List current baselines for all cases in SUITE."""
    suite_path = Path(suite)
    try:
        eval_suite = load_suite(suite_path)
    except FileNotFoundError:
        click.echo(f"Error: Suite file not found: {suite}", err=True)
        sys.exit(2)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    exec_store, art_store = _get_stores()
    try:
        asyncio.run(_baselines_async(eval_suite, json_out, exec_store))
    finally:
        asyncio.run(exec_store.close())


async def _baselines_async(eval_suite: Any, json_out: bool, exec_store: Any) -> None:
    import json as json_mod

    baselines = await exec_store.get_baselines(eval_suite.name)

    rows = []
    for case in eval_suite.cases:
        run_id = baselines.get(case.id)
        rows.append({
            "case_id": case.id,
            "run_id": run_id,
            "missing": run_id is None,
        })

    if json_out:
        click.echo(json_mod.dumps({"suite": eval_suite.name, "baselines": rows}, indent=2))
        return

    click.echo(f"Baselines for suite: {eval_suite.name}")
    for row in rows:
        status = "MISSING" if row["missing"] else row["run_id"]
        click.echo(f"  {row['case_id']}: {status}")
