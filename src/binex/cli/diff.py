"""CLI `binex diff` command — compare two runs."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from binex.cli import get_stores, has_rich


@click.command("diff", epilog="""\b
Examples:
  binex diff <run_a> <run_b>            Compare two runs
  binex diff <run_a> <run_b> --json     Machine-readable output
  binex diff <run_a> <run_b> --semantic Analyze meaningful vs cosmetic changes (uses a model)
""")
@click.argument("run_a")
@click.argument("run_b")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
@click.option("--semantic", is_flag=True,
              help="Ask a model whether changes are meaningful or cosmetic "
                   "(opt-in, spends tokens)")
@click.option("--semantic-model", default=None,
              help="Model for --semantic (default: BINEX_JUDGE_MODEL or a cheap default; "
                   "use e.g. ollama/llama3 for fully local)")
@click.option("--yes", "-y", "assume_yes", is_flag=True,
              help="Skip the cost-confirmation prompt for --semantic")
def diff_cmd(
    run_a: str, run_b: str, json_out: bool, rich_out: bool | None,
    semantic: bool, semantic_model: str | None, assume_yes: bool,
) -> None:
    """Compare two runs side-by-side."""
    if rich_out is None:
        rich_out = has_rich()
    try:
        result = asyncio.run(_run_diff(run_a, run_b))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    semantic_verdicts: dict[str, Any] | None = None
    if semantic:
        semantic_verdicts = _do_semantic(result, semantic_model, assume_yes, json_out)

    if json_out:
        if semantic_verdicts is not None:
            result = {**result, "semantic": _semantic_to_json(semantic_verdicts)}
        click.echo(json.dumps(result, default=str, indent=2))
    elif rich_out:
        from binex.trace.diff_rich import format_diff_rich
        format_diff_rich(result)
    else:
        from binex.trace.diff import format_diff
        click.echo(format_diff(result))

    if semantic_verdicts and not json_out:
        _print_semantic(semantic_verdicts)


async def _run_diff(run_a: str, run_b: str) -> dict[str, Any]:
    from binex.trace.diff import diff_runs

    exec_store, art_store = get_stores()
    try:
        return await diff_runs(exec_store, art_store, run_a, run_b)
    finally:
        await exec_store.close()


# ---------------------------------------------------------------------------
# Semantic diff (issue #71)
# ---------------------------------------------------------------------------

def _do_semantic(
    result: dict[str, Any], model: str | None, assume_yes: bool, json_out: bool,
) -> dict[str, Any] | None:
    """Estimate cost, confirm, run the judge. Returns {node_id: verdict} or None."""
    from binex.eval.judge import resolve_judge_model
    from binex.trace.semantic_diff import analyze_diff, changed_pairs
    from binex.trace.semantic_judge import estimate_cost, make_semantic_judge

    resolved = resolve_judge_model(model)
    pairs = changed_pairs(result)
    if not pairs:
        click.echo("No content changes to analyze semantically.", err=True)
        return None

    est = estimate_cost(pairs, resolved)
    cost_str = f"~${est.cost:.4f}" if est.cost is not None else "unknown (unpriced model)"
    # Always shown (on stderr) — Binex spending tokens is never silent.
    click.echo(
        f"Semantic analysis: {est.calls} judge call(s) on '{resolved}', "
        f"~{est.total_tokens} tokens, estimated cost {cost_str}.",
        err=True,
    )
    if not assume_yes and not click.confirm("Proceed?", default=False, err=True):
        click.echo("Skipped semantic analysis.", err=True)
        return None

    judge = make_semantic_judge(resolved)
    return asyncio.run(analyze_diff(result, judge))


def _semantic_to_json(verdicts: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "node_id": v.node_id,
            "meaningful": v.meaningful,
            "summary": v.summary,
            "error": v.error,
            "questions": [
                {"key": q.key, "changed": q.changed,
                 "confidence": q.confidence, "reason": q.reason}
                for q in v.questions
            ],
        }
        for v in verdicts.values()
    ]


def _print_semantic(verdicts: dict[str, Any]) -> None:
    """Render the semantic verdicts below the textual diff."""
    click.echo("\nSemantic analysis")
    for v in verdicts.values():
        marker = "⚠ " if v.meaningful else "· "
        click.echo(f"  {marker}{v.node_id}: {v.summary}")
        for q in v.questions:
            if q.changed:
                click.echo(f"      - {q.key}: changed ({q.confidence}) — {q.reason}")
