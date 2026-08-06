"""CLI `binex bisect` command — find divergence between two runs."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click

from binex.cli import get_stores, has_rich
from binex.cli.bisect_format import (
    _RICH_COLORS,
    _content_preview,
    _describe_change,
    _extract_preview,
    _format_diff_line_rich,
    _format_latency,
    _node_icon,
    _node_word,
    _print_footer_plain,
    _print_node_details_plain,
    _render_footer_rich,
    _render_verdict_rich,
)
from binex.runtime.replay import ImportedRunError, ensure_replayable


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


class BisectGroup(click.Group):
    """`binex bisect <good> <bad>` (node-level) still works alongside subcommands.

    When the first argument isn't a known subcommand (or an option), it's routed
    to the default ``runs`` subcommand — preserving the original CLI.
    """

    def resolve_command(
        self, ctx: click.Context, args: list[str],
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            args = ["runs", *args]
        return super().resolve_command(ctx, args)


@click.command("runs")
@click.argument("good_run_id")
@click.argument("bad_run_id")
@click.option(
    "--threshold", type=float, default=0.9, show_default=True,
    help="Content similarity threshold (0.0-1.0). Nodes below this are marked as diverged.",
)
@click.option(
    "--json-output", "--json", "json_out",
    is_flag=True, help="Output as JSON",
)
@click.option(
    "--diff", "show_diff",
    is_flag=True, help="Show full unified diffs instead of preview",
)
@click.option(
    "--rich/--no-rich", "rich_out",
    default=None, help="Rich output (auto-detected)",
)
def runs_cmd(
    good_run_id: str,
    bad_run_id: str,
    threshold: float,
    json_out: bool,
    show_diff: bool,
    rich_out: bool | None,
) -> None:
    """Find the first node where two runs diverge."""
    if rich_out is None:
        rich_out = has_rich()
    try:
        report = asyncio.run(
            _run_bisect(good_run_id, bad_run_id, threshold),
        )
    except ImportedRunError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    from binex.trace.bisect import bisect_report_to_dict  # type: ignore[attr-defined]

    result = bisect_report_to_dict(report)

    if json_out:
        click.echo(json.dumps(result, default=str, indent=2))
    elif rich_out:
        _print_rich(report, show_diff)
    else:
        _print_plain(report, show_diff)


async def _run_bisect(
    good_run_id: str, bad_run_id: str, threshold: float,
) -> Any:
    from binex.trace.bisect import bisect_report

    exec_store, art_store = _get_stores()
    try:
        for run_id in (good_run_id, bad_run_id):
            run = await exec_store.get_run(run_id)
            if run is not None:
                ensure_replayable(run, operation="bisect")
        return await bisect_report(
            exec_store, art_store,
            good_run_id, bad_run_id, threshold,
        )
    finally:
        await exec_store.close()


# ---------------------------------------------------------------------------
# Plain text output
# ---------------------------------------------------------------------------

def _verdict_plain(dp: Any, report: Any) -> None:
    """Print the verdict section in plain text."""
    if dp is None:
        click.echo(
            "\u2713 No differences found "
            "\u2014 runs are identical."
        )
    elif dp.divergence_type == "status":
        pattern = ""
        if report.error_context:
            pattern = f" ({report.error_context.pattern})"
        click.echo(
            f"\u2717 Node \"{dp.node_id}\" "
            f"{dp.bad_status}{pattern}"
        )
        if report.downstream_impact:
            n = len(report.downstream_impact)
            word = "node" if n == 1 else "nodes"
            click.echo(
                f"  Caused {n} downstream {word} to cancel."
            )
    else:
        desc = _describe_change(dp.similarity)
        click.echo(f"\u26a0 Node \"{dp.node_id}\" output {desc}")


def _node_marker_plain(nc: Any, dp: Any, downstream_set: set[str]) -> str:
    """Return the marker suffix for a pipeline node."""
    if dp and nc.node_id == dp.node_id:
        return "  \u2190 root cause"
    if nc.node_id in downstream_set:
        return "  \u2190 affected"
    return ""


def _print_plain(report: Any, show_diff: bool = False) -> None:
    """Print intuitive plain text bisect output."""
    # Header
    click.echo(f"Bisect: {report.workflow_name}")
    click.echo(
        f"good {report.good_run_id}  vs  bad {report.bad_run_id}"
    )
    click.echo()

    dp = report.divergence_point
    downstream_set = set(report.downstream_impact)

    _verdict_plain(dp, report)
    click.echo()

    # Pipeline
    click.echo("Pipeline")
    total = len(report.node_map)
    for i, nc in enumerate(report.node_map):
        is_last = i == total - 1
        connector = "\u2514\u2500\u2500" if is_last else "\u251c\u2500\u2500"
        cont = "   " if is_last else "\u2502  "

        icon = _node_icon(nc.status)
        word = _node_word(nc.status, nc.bad_status)
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)
        marker = _node_marker_plain(nc, dp, downstream_set)

        click.echo(
            f"{connector} {nc.node_id:<12} "
            f"{icon} {word:<10} "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        # Nested details
        _print_node_details_plain(nc, report, cont, show_diff)

    # Footer
    click.echo()
    _print_footer_plain(report)


# ---------------------------------------------------------------------------
# Rich output
# ---------------------------------------------------------------------------

def _node_marker_rich(nc: Any, dp: Any, downstream_set: set[str]) -> str:
    """Return the Rich marker suffix for a pipeline node."""
    if dp and nc.node_id == dp.node_id:
        return "  [red bold]\u2190 root cause[/red bold]"
    if nc.node_id in downstream_set:
        return "  [dim]\u2190 affected[/dim]"
    return ""


def _print_node_error_rich(console: Any, nc: Any, report: Any, cont: str) -> None:
    """Print error context for a node in Rich format."""
    if (
        report.error_context
        and report.error_context.node_id == nc.node_id
    ):
        console.print(
            f"{cont}\u2514\u2500\u2500 "
            f"[red]{report.error_context.error_message}"
            f"[/red]"
        )


def _print_node_diff_rich(console: Any, nc: Any, cont: str, show_diff: bool) -> None:
    """Print content diff or preview for a node in Rich format."""
    if not (nc.content_diff and nc.status == "content_diff"):
        return
    if show_diff:
        for line in nc.content_diff:
            formatted = _format_diff_line_rich(line)
            console.print(f"{cont}{formatted}")
    else:
        good_lines, bad_lines = _extract_preview(nc.content_diff)
        if good_lines:
            preview = _content_preview("\n".join(good_lines), 100)
            console.print(
                f"{cont}\u251c\u2500\u2500 "
                f"[green]good: \"{preview}\"[/green]"
            )
        if bad_lines:
            preview = _content_preview("\n".join(bad_lines), 100)
            console.print(
                f"{cont}\u2514\u2500\u2500 "
                f"[red]bad:  \"{preview}\"[/red]"
            )


def _print_rich(report: Any, show_diff: bool = False) -> None:
    """Print rich formatted bisect output."""
    from binex.cli.ui import get_console

    console = get_console()

    dp = report.divergence_point
    downstream_set = set(report.downstream_impact)

    # Header
    console.print(
        f"[bold]Bisect:[/bold] {report.workflow_name}"
    )
    console.print(
        f"[cyan]good[/cyan] {report.good_run_id}  vs  "
        f"[cyan]bad[/cyan] {report.bad_run_id}"
    )
    console.print()

    # Verdict
    _render_verdict_rich(console, report, dp)
    console.print()

    # Pipeline
    console.print("[bold]Pipeline[/bold]")
    total = len(report.node_map)
    for i, nc in enumerate(report.node_map):
        is_last = i == total - 1
        connector = (
            "\u2514\u2500\u2500" if is_last
            else "\u251c\u2500\u2500"
        )
        cont = "   " if is_last else "\u2502  "

        icon = _node_icon(nc.status)
        word = _node_word(nc.status, nc.bad_status)
        color = _RICH_COLORS.get(nc.status, "dim")
        lat_g = _format_latency(nc.latency_good_ms)
        lat_b = _format_latency(nc.latency_bad_ms)
        marker = _node_marker_rich(nc, dp, downstream_set)

        console.print(
            f"{connector} [bold]{nc.node_id:<12}[/bold] "
            f"[{color}]{icon} {word:<10}[/{color}] "
            f"{lat_g} \u2192 {lat_b}"
            f"{marker}"
        )

        _print_node_error_rich(console, nc, report, cont)
        _print_node_diff_rich(console, nc, cont, show_diff)

    # Footer
    console.print()
    _render_footer_rich(console, report)


# ---------------------------------------------------------------------------
# History bisect (issue #72): find the commit that broke pipeline quality
# ---------------------------------------------------------------------------

@click.command("history", epilog="""\b
Examples:
  binex bisect history -w flow.yaml --good v1.0 --bad HEAD
  binex bisect history -w flow.yaml --good run_abc --bad run_xyz
  binex bisect history -w flow.yaml --good abc123 --bad HEAD \\
      --baseline run_golden --min-similarity 0.9
""")
@click.option("-w", "--workflow", "workflow", required=True,
              type=click.Path(exists=True),
              help="Workflow file to run at each probed commit")
@click.option("--good", "good", required=True,
              help="Known-good commit/ref, or a run ID (resolved to its commit)")
@click.option("--bad", "bad", required=True,
              help="Known-bad commit/ref, or a run ID (resolved to its commit)")
@click.option("--var", multiple=True, help="Variable substitution key=value")
@click.option("--baseline", default=None,
              help="Golden run ID for a diff criterion (else assertions only)")
@click.option("--min-similarity", type=float, default=1.0, show_default=True,
              help="Content-similarity floor when --baseline is used")
@click.option("--max-latency-delta-ms", type=float, default=None,
              help="Latency-growth ceiling when --baseline is used")
@click.option("--max-cost-delta", type=float, default=None,
              help="Cost-growth ceiling when --baseline is used")
@click.option("--json-output", "--json", "json_out", is_flag=True,
              help="Output as JSON")
def history_cmd(
    workflow: str,
    good: str,
    bad: str,
    var: tuple[str, ...],
    baseline: str | None,
    min_similarity: float,
    max_latency_delta_ms: float | None,
    max_cost_delta: float | None,
    json_out: bool,
) -> None:
    """Binary-search git history for the commit that broke pipeline quality.

    Re-runs the workflow at each probed commit in an isolated git worktree (your
    working tree is never touched) and judges pass/fail with eval assertions
    (and an optional baseline diff). Prints the first bad commit.
    """
    from binex.bisect_history import BisectError
    from binex.eval.golden import EvalThresholds

    thresholds = EvalThresholds(
        min_similarity=min_similarity,
        max_latency_delta_ms=max_latency_delta_ms,
        max_cost_delta=max_cost_delta,
    )
    try:
        result = asyncio.run(_run_history(
            workflow, good, bad, _parse_vars(var), baseline, thresholds,
        ))
    except BisectError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)

    if json_out:
        click.echo(json.dumps({
            "first_bad": result.first_bad,
            "tested": result.tested,
            "skipped": result.skipped,
            "indeterminate": result.indeterminate,
            "probes": [
                {"commit": p.commit, "verdict": p.verdict, "detail": p.detail}
                for p in result.probes
            ],
        }, indent=2))
    else:
        _print_history(result)

    sys.exit(0 if result.first_bad else 1)


def _parse_vars(var_tuples: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for v in var_tuples:
        if "=" not in v:
            raise click.BadParameter(f"Invalid var format: {v} (expected key=value)")
        key, value = v.split("=", 1)
        result[key] = value
    return result


async def _resolve_endpoint(ref: str, repo_root: str) -> str:
    """Resolve a --good/--bad value: a run ID → its stored git_sha, else a git ref."""
    from binex.bisect_history import resolve_ref

    if ref.startswith("run_"):
        exec_store, _ = _get_stores()
        try:
            run = await exec_store.get_run(ref)
        finally:
            await exec_store.close()
        if run is None:
            from binex.bisect_history import BisectError
            raise BisectError(f"run '{ref}' not found")
        if not getattr(run, "git_sha", None):
            from binex.bisect_history import BisectError
            raise BisectError(
                f"run '{ref}' has no recorded commit (predates git provenance)"
            )
        return str(run.git_sha)
    return resolve_ref(ref, repo_root)


async def _run_history(
    workflow: str, good: str, bad: str,
    user_vars: dict[str, str], baseline: str | None, thresholds: Any,
) -> Any:
    import os

    from binex.bisect_history import (
        BisectError,
        bisect_history,
        is_clean_worktree,
        list_commits_between,
        make_git_probe,
    )

    repo_root = _repo_root_of(os.path.abspath(workflow))
    if repo_root is None:
        raise BisectError(f"workflow '{workflow}' is not inside a git repository")

    if not is_clean_worktree(repo_root):
        click.echo(
            "Warning: working tree has uncommitted changes; "
            "bisect tests committed history only.",
            err=True,
        )

    good_sha = await _resolve_endpoint(good, repo_root)
    bad_sha = await _resolve_endpoint(bad, repo_root)
    workflow_rel = os.path.relpath(os.path.abspath(workflow), repo_root)

    commits = list_commits_between(good_sha, bad_sha, repo_root)

    probe = make_git_probe(
        repo_root, workflow_rel,
        user_vars=user_vars, baseline=baseline, thresholds=thresholds,
        on_probe=lambda c, v, d: click.echo(f"  probe {c[:12]}: {v} — {d}", err=True),
    )
    return await bisect_history(commits, probe)


def _repo_root_of(path: str) -> str | None:
    """Return the git top-level directory containing ``path``, or None."""
    import subprocess

    start = path if Path(path).is_dir() else str(Path(path).parent)
    try:
        result = subprocess.run(
            ["git", "-C", start, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _print_history(result: Any) -> None:
    """Human-readable history-bisect output."""
    click.echo(f"Tested {result.tested} commit(s), {len(result.skipped)} skipped.")
    if result.first_bad:
        click.echo(f"\n✗ First bad commit: {result.first_bad}")
        for p in result.probes:
            if p.commit == result.first_bad:
                click.echo(f"  {p.detail}")
                break
        click.echo("\nTip: run 'binex bisect <good_run> <bad_run>' to locate the "
                   "offending node within that commit.")
    elif result.indeterminate:
        click.echo("\n? Indeterminate — too many commits could not be evaluated "
                   "(skipped). Narrow the range or check workflow availability.")
    else:
        click.echo("\n✓ No bad commit found in range — all probes passed.")


bisect_group = BisectGroup(
    name="bisect",
    help="Locate a regression: across nodes (default) or across git history.",
)
bisect_group.add_command(runs_cmd, "runs")
bisect_group.add_command(history_cmd, "history")
