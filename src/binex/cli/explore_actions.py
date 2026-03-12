"""Explore action handlers — trace, graph, debug, cost, artifacts, node, diagnose, diff, bisect."""

from __future__ import annotations

import click

from binex.cli import has_rich
from binex.cli.explore_ui import (
    _print_artifacts_table,
    _render_diagnose_plain,
    _render_diagnose_rich,
    _render_node_list_plain,
    _render_node_list_rich,
    _render_node_plain,
    _render_node_rich,
    _show_artifact_detail,
    _show_lineage,
)
from binex.cli.explore_utils import _short_id, _time_ago


async def _action_trace(exec_store, run_id: str) -> None:
    """Show execution timeline with node drill-down."""
    records = await exec_store.list_records(run_id)
    if not records:
        click.echo("  No records found.")
        return
    records.sort(key=lambda r: r.timestamp)

    if has_rich():
        try:
            from binex.trace.trace_rich import (
                format_trace_node_rich,
                format_trace_rich,
            )
            await format_trace_rich(exec_store, run_id)
            await _trace_node_drill_down(records, format_trace_node_rich)
            return
        except ImportError:
            pass

    from binex.trace.tracer import generate_timeline
    output = await generate_timeline(exec_store, run_id)
    click.echo(output)


async def _trace_node_drill_down(records, format_node_fn) -> None:
    """Interactive node selection loop for trace view."""
    while True:
        choice = click.prompt(
            "  Select node # (or Enter=back, q=back to runs)", default="",
        )
        key = choice.strip().lower()
        if key in ("", "b"):
            return
        if key == "q":
            raise SystemExit(0)
        try:
            idx = int(key) - 1
            if 0 <= idx < len(records):
                await format_node_fn(records[idx])
            else:
                click.echo(f"  Invalid: enter 1-{len(records)}")
        except ValueError:
            click.echo(f"  Invalid: enter 1-{len(records)}")


async def _action_graph(exec_store, run_id: str) -> None:
    """Show DAG visualization."""
    from binex.cli.trace import _build_graph_from_records, _render_dag

    records = await exec_store.list_records(run_id)
    if not records:
        click.echo("  No records found.")
        return

    nodes, edges = _build_graph_from_records(records)
    await _enrich_graph_from_workflow(exec_store, run_id, nodes, edges)

    if has_rich():
        try:
            from binex.trace.trace_rich import format_trace_graph_rich
            await format_trace_graph_rich(records, nodes, edges)
            return
        except ImportError:
            pass

    click.echo("DAG:")
    _render_dag(nodes, edges, set(), click.echo)


async def _enrich_graph_from_workflow(
    exec_store, run_id: str, nodes: dict, edges: list,
) -> None:
    """Add unexecuted nodes from workflow spec to the graph."""
    run = await exec_store.get_run(run_id)
    if not run or not run.workflow_path:
        return
    try:
        from binex.workflow_spec.loader import load_workflow
        spec = load_workflow(run.workflow_path)
        _merge_spec_into_graph(spec, nodes, edges)
    except Exception:
        pass  # Workflow file may be missing or changed


def _merge_spec_into_graph(spec, nodes: dict, edges: list) -> None:
    """Merge workflow spec nodes/edges into existing graph data."""
    for node_id, node_spec in spec.nodes.items():
        if node_id not in nodes:
            nodes[node_id] = f"[?] {node_id} ({node_spec.agent})"
        for dep in node_spec.depends_on:
            if dep in nodes and (dep, node_id) not in edges:
                edges.append((dep, node_id))


async def _action_debug(exec_store, art_store, run_id: str) -> None:
    """Show debug report."""
    from binex.trace.debug_report import build_debug_report, format_debug_report

    report = await build_debug_report(exec_store, art_store, run_id)
    if report is None:
        click.echo("  No debug data available.")
        return

    if has_rich():
        try:
            from binex.trace.debug_rich import format_debug_report_rich
            format_debug_report_rich(report)
            return
        except ImportError:
            pass

    click.echo(format_debug_report(report))


async def _action_cost(exec_store, run_id: str) -> None:
    """Show cost breakdown."""
    from binex.cli.cost import print_cost_text

    cost_summary = await exec_store.get_run_cost_summary(run_id)
    cost_records = await exec_store.list_costs(run_id)
    print_cost_text(run_id, cost_summary, cost_records)


async def _action_artifacts(exec_store, art_store, run_id: str) -> None:
    """Artifact sub-browser: list → select → detail + lineage."""
    artifacts = await art_store.list_by_run(run_id)
    if not artifacts:
        click.echo(f"  No artifacts for run '{_short_id(run_id)}'.")
        return

    while True:
        click.echo()
        _print_artifacts_table(artifacts, run_id)
        click.echo()

        choice = click.prompt(
            "  Select artifact (or b=back)", default="b",
        )
        if choice.lower() == "b":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(artifacts):
                _show_artifact_detail(artifacts[idx])
                # Offer lineage
                lc = click.prompt(
                    "  [l] lineage  [b] back", default="b",
                )
                if lc.lower() == "l":
                    await _show_lineage(art_store, artifacts[idx].id)
                continue
        except ValueError:
            pass
        click.echo(f"  Invalid choice. Enter 1-{len(artifacts)} or b.")


async def _action_node(exec_store, art_store, run_id: str, records) -> list:
    """Show numbered list of nodes, select one for detail. Returns node artifacts."""
    if not records:
        click.echo("  No execution records.")
        return []

    click.echo()
    if has_rich():
        _render_node_list_rich(records)
    else:
        _render_node_list_plain(records)
    click.echo()

    choice = click.prompt("  Select node (or b=back)", default="b")
    if choice.lower() == "b":
        return []

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(records)):
            click.echo(f"  Invalid choice. Enter 1-{len(records)} or b.")
            return []
    except ValueError:
        click.echo(f"  Invalid choice. Enter 1-{len(records)} or b.")
        return []

    rec = records[idx]
    artifacts = await art_store.list_by_run(run_id)
    node_arts = [
        a for a in artifacts
        if a.lineage and a.lineage.produced_by == rec.task_id
    ]
    costs = await exec_store.list_costs(run_id)
    node_total_cost = sum(c.cost for c in costs if c.task_id == rec.task_id)

    click.echo()
    if has_rich():
        _render_node_rich(rec, node_arts, node_total_cost)
    else:
        _render_node_plain(rec, node_arts, node_total_cost)
    return node_arts


async def _action_diagnose(exec_store, art_store, run_id: str) -> None:
    """Run root-cause analysis on the current run."""
    from binex.trace.diagnose import diagnose_run

    try:
        report = await diagnose_run(exec_store, art_store, run_id)
    except ValueError as e:
        click.echo(f"  Error: {e}")
        return

    if has_rich():
        _render_diagnose_rich(report)
    else:
        _render_diagnose_plain(report)


async def _action_diff(exec_store, art_store, run_id: str, run) -> None:
    """Compare current run with another run."""
    other_id = await _pick_other_run(exec_store, run_id, run.workflow_name)
    if not other_id:
        click.echo("  Diff cancelled.")
        return

    from binex.trace.diff import diff_runs

    try:
        result = await diff_runs(exec_store, art_store, run_id, other_id)
    except ValueError as e:
        click.echo(f"  Error: {e}")
        return

    if has_rich():
        from binex.trace.diff_rich import format_diff_rich
        format_diff_rich(result)
    else:
        from binex.trace.diff import format_diff
        click.echo(format_diff(result))


async def _action_bisect(exec_store, art_store, run_id: str, run) -> None:
    """Find divergence point between current run (bad) and another run (good)."""
    click.echo("  Current run = bad run. Select the good run:")
    good_id = await _pick_other_run(exec_store, run_id, run.workflow_name)
    if not good_id:
        click.echo("  Bisect cancelled.")
        return

    from binex.trace.bisect import bisect_report as _bisect_report

    try:
        report = await _bisect_report(
            exec_store, art_store, good_id, run_id,
        )
    except ValueError as e:
        click.echo(f"  Error: {e}")
        return

    if has_rich():
        from binex.cli.bisect import _print_rich
        _print_rich(report)
    else:
        from binex.cli.bisect import _print_plain
        _print_plain(report)


async def _pick_other_run(exec_store, current_run_id: str, workflow_name: str) -> str | None:
    """Let user pick another run of the same workflow. Returns run_id or None."""
    all_runs = await exec_store.list_runs()
    same_wf = [
        r for r in all_runs
        if r.workflow_name == workflow_name and r.run_id != current_run_id
    ]
    same_wf.sort(key=lambda r: r.started_at, reverse=True)
    same_wf = same_wf[:10]

    if not same_wf:
        click.echo("  No other runs of this workflow found.")
        manual = click.prompt("  Enter run_id manually (or q=cancel)", default="q")
        return None if manual.strip().lower() == "q" else manual.strip()

    click.echo()
    if has_rich():
        from binex.cli.ui import get_console, make_table, status_text

        table = make_table(
            ("#", {"style": "dim", "width": 4, "justify": "right"}),
            ("Run ID", {"style": "cyan", "min_width": 16}),
            ("Status", {"min_width": 10}),
            ("When", {"style": "dim", "min_width": 8}),
            title=f"Other runs of '{workflow_name}'",
        )
        for i, r in enumerate(same_wf, 1):
            table.add_row(
                str(i), _short_id(r.run_id),
                status_text(r.status), _time_ago(r.started_at),
            )
        get_console().print(table)
    else:
        click.echo(f"  Other runs of '{workflow_name}':")
        for i, r in enumerate(same_wf, 1):
            click.echo(
                f"  {i:>3})  {_short_id(r.run_id):<18} {r.status:<12} "
                f"{_time_ago(r.started_at)}"
            )
    click.echo()

    choice = click.prompt(
        "  Select run # or enter run_id (q=cancel)", default="q",
    )
    if choice.strip().lower() == "q":
        return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(same_wf):
            return same_wf[idx].run_id
    except ValueError:
        pass
    # Treat as manual run_id
    return choice.strip() if choice.strip() else None
