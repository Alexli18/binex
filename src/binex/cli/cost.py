"""CLI `binex cost` command group — show and history subcommands."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from binex.cli import get_stores


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


async def build_cost_data(exec_store: Any, run_id: str) -> tuple[Any, Any, Any]:
    """Fetch cost summary and records for reuse by explore dashboard."""
    run = await exec_store.get_run(run_id)
    if run is None:
        return None, None, []
    cost_summary = await exec_store.get_run_cost_summary(run_id)
    cost_records = await exec_store.list_costs(run_id)
    return run, cost_summary, cost_records


@click.group("cost", epilog="""\b
Examples:
  binex cost show <run_id>           Cost breakdown by node
  binex cost history <run_id>        Chronological cost events
  binex cost show <run_id> --json    Machine-readable output
""")
def cost_group() -> None:
    """Inspect cost data for workflow runs."""


@cost_group.command("show")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def cost_show_cmd(run_id: str, json_out: bool) -> None:
    """Display cost breakdown for a run."""
    asyncio.run(_cost_show(run_id, json_out))


@cost_group.command("simulate", epilog="""\b
Examples:
  binex cost simulate <run_id> --node writer --model claude-3-haiku-20240307
  binex cost simulate <run_id> --all-nodes gpt-4o-mini
""")
@click.argument("run_id")
@click.option("--node", "node", default=None, help="Node to swap (with --model)")
@click.option("--model", "model", default=None, help="Target model for --node")
@click.option("--all-nodes", "all_nodes_model", default=None,
              help="Re-price every node with this model")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def cost_simulate_cmd(
    run_id: str, node: str | None, model: str | None,
    all_nodes_model: str | None, json_out: bool,
) -> None:
    """Estimate what a run would cost on a different model (no LLM calls)."""
    if all_nodes_model:
        if node or model:
            raise click.UsageError("--all-nodes cannot be combined with --node/--model")
    elif node and model:
        pass
    else:
        raise click.UsageError("provide either --all-nodes MODEL or --node NODE --model MODEL")
    asyncio.run(_cost_simulate(run_id, node, model, all_nodes_model, json_out))


async def _cost_show(run_id: str, json_out: bool) -> None:
    execution_store, _ = _get_stores()
    try:
        run = await execution_store.get_run(run_id)
        if run is None:
            click.echo(f"Error: Run '{run_id}' not found.", err=True)
            click.echo("Tip: use 'binex explore' to browse available runs.", err=True)
            sys.exit(1)

        cost_summary = await execution_store.get_run_cost_summary(run_id)
        cost_records = await execution_store.list_costs(run_id)

        if json_out:
            _print_cost_json(run_id, cost_summary, cost_records)
        else:
            print_cost_text(run_id, cost_summary, cost_records)
    finally:
        await execution_store.close()


def _descendants(dag: Any, node: str) -> set[str]:
    """All nodes transitively reachable from ``node`` via forward edges."""
    seen: set[str] = set()
    stack = list(dag.dependents(node))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(dag.dependents(current))
    return seen


async def _load_dag(execution_store: Any, run: Any) -> Any | None:
    """Rebuild the run's DAG from its stored workflow snapshot (best-effort)."""
    import yaml  # type: ignore[import-untyped]

    from binex.graph.dag import DAG
    from binex.models.workflow import WorkflowSpec

    if not run.workflow_hash:
        return None
    snapshot = await execution_store.get_workflow_snapshot(run.workflow_hash)
    if not snapshot or "content" not in snapshot:
        return None
    try:
        spec = WorkflowSpec(**yaml.safe_load(snapshot["content"]))
        return DAG.from_workflow(spec)
    except Exception:
        return None


async def _cost_simulate(
    run_id: str, node: str | None, model: str | None,
    all_nodes_model: str | None, json_out: bool,
) -> None:
    from binex.cost_simulation import simulate

    execution_store, _ = _get_stores()
    try:
        run = await execution_store.get_run(run_id)
        if run is None:
            click.echo(f"Error: Run '{run_id}' not found.", err=True)
            sys.exit(1)

        cost_records = await execution_store.list_costs(run_id)
        all_node_ids = {rec.task_id for rec in cost_records}

        if all_nodes_model:
            target_model = all_nodes_model
            swapped = set(all_node_ids)
            downstream: set[str] = set()
        else:
            assert node is not None and model is not None
            if node not in all_node_ids:
                click.echo(
                    f"Error: node '{node}' has no cost records in run '{run_id}'.",
                    err=True,
                )
                sys.exit(1)
            target_model = model
            swapped = {node}
            dag = await _load_dag(execution_store, run)
            downstream = _descendants(dag, node) & all_node_ids if dag else set()

        result = simulate(
            cost_records, target_model=target_model,
            swapped_nodes=swapped, downstream_nodes=downstream,
        )

        graph_used = bool(downstream) or bool(all_nodes_model)
        if json_out:
            _print_simulation_json(run_id, result)
        else:
            _print_simulation_text(run_id, result, dag_available=graph_used)
    finally:
        await execution_store.close()


def _print_simulation_json(run_id: str, result: Any) -> None:
    data = {
        "run_id": run_id,
        "target_model": result.target_model,
        "original_total": round(result.orig_total, 6),
        "estimated_total_low": round(result.est_low_total, 6),
        "estimated_total_high": round(result.est_high_total, 6),
        "disclaimer": result.disclaimer,
        "nodes": [
            {
                "node": n.node_id,
                "affected": n.affected,
                "original_cost": round(n.orig_cost, 6),
                "estimated_low": round(n.est_low, 6),
                "estimated_high": round(n.est_high, 6),
                "model_from": n.model_from,
                "model_to": n.model_to,
                "priced": n.priced,
            }
            for n in result.nodes
        ],
    }
    click.echo(json.dumps(data, indent=2))


def _print_simulation_text(run_id: str, result: Any, *, dag_available: bool) -> None:
    click.echo(f"Cost simulation for run {run_id} → {result.target_model}")
    click.echo("")
    for n in result.nodes:
        tag = {"swapped": "→", "downstream": "~", "unchanged": " "}[n.affected]
        note = "" if n.priced else "  (unpriced model — kept original)"
        rng = (
            f"${n.est_low:.4f}"
            if abs(n.est_high - n.est_low) < 1e-9
            else f"${n.est_low:.4f}–${n.est_high:.4f}"
        )
        click.echo(f"  {tag} {n.node_id:<20} ${n.orig_cost:.4f} → {rng}{note}")
    click.echo("")
    click.echo(
        f"Total: ${result.orig_total:.4f} → "
        f"${result.est_low_total:.4f}–${result.est_high_total:.4f} (estimated)"
    )
    if not dag_available and any(n.affected == "swapped" for n in result.nodes):
        click.echo(
            "Note: workflow graph unavailable — downstream cost impact not estimated.",
            err=True,
        )
    click.echo(f"\n{result.disclaimer}", err=True)


def _print_cost_json(run_id: str, cost_summary: Any, cost_records: Any) -> None:
    """Format cost data as JSON."""
    data = {
        "run_id": run_id,
        "total_cost": cost_summary.total_cost,
        "currency": cost_summary.currency,
    }
    if cost_summary.budget is not None:
        data["budget"] = cost_summary.budget
        data["remaining_budget"] = cost_summary.remaining_budget
    data["nodes"] = [
        {
            k: v for k, v in {
                "task_id": r.task_id,
                "cost": r.cost,
                "source": r.source,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "model": r.model,
                "node_budget": r.node_budget,
            }.items() if v is not None
        }
        for r in cost_records
    ]
    click.echo(json.dumps(data, default=str, indent=2))


def _print_cost_rich(run_id: str, cost_summary: Any) -> None:
    """Render cost data using Rich panels and tables."""
    from rich.console import Group
    from rich.text import Text

    from binex.cli.ui import cost_bar, get_console, make_header, make_panel, make_table

    header = make_header(run=run_id)

    max_cost = max(
        (v for v in cost_summary.node_costs.values()), default=0,
    )
    table = make_table(
        ("Node", {"style": "bold", "min_width": 14}),
        ("Cost", {"justify": "right"}),
        ("", {"min_width": 22}),  # bar column
        title="Cost Breakdown",
    )
    for task_id, cost in cost_summary.node_costs.items():
        cost_style = "bold" if cost > 0 else "dim"
        table.add_row(
            task_id,
            Text(f"${cost:.4f}", style=cost_style),
            cost_bar(cost, max_cost),
        )

    summary = _build_cost_summary_text(cost_summary)

    panel = make_panel(
        Group(header, Text(), table, Text(), summary),
        title="Cost",
        subtitle=f"run: {run_id}",
    )
    get_console().print(panel)


def _build_cost_summary_text(cost_summary: Any) -> Any:
    """Build Rich Text summary line for cost display."""
    from rich.text import Text

    summary = Text()
    summary.append("Total: ", style="dim")
    summary.append(f"${cost_summary.total_cost:.4f}", style="bold green")
    if cost_summary.budget is not None:
        remaining = cost_summary.remaining_budget or 0.0
        summary.append(f"  ·  Budget: ${cost_summary.budget:.2f}", style="dim")
        summary.append(f"  ·  Remaining: ${remaining:.2f}", style="dim")
    return summary


def _print_cost_plain(run_id: str, cost_summary: Any, cost_records: Any) -> None:
    """Render cost data as plain text."""
    click.echo(f"Run: {run_id}")
    click.echo(f"\nTotal cost: ${cost_summary.total_cost:.2f}")
    if cost_summary.budget is not None:
        click.echo(f"Budget: ${cost_summary.budget:.2f}")
        remaining = cost_summary.remaining_budget or 0.0
        click.echo(f"Remaining: ${remaining:.2f}")
    click.echo("\nNode breakdown:")
    billed_nodes = {k: v for k, v in cost_summary.node_costs.items() if v > 0}
    if not billed_nodes:
        click.echo("  (no billed nodes)")
    for task_id, cost in billed_nodes.items():
        _print_node_cost_line(cost_records, task_id, cost)


def _print_node_cost_line(cost_records: Any, task_id: str, cost: float) -> None:
    """Print a single node cost line with optional budget info."""
    node_budget = _find_node_budget(cost_records, task_id)
    if node_budget is not None:
        remaining = node_budget - cost
        click.echo(
            f"  {task_id:<20} ${cost:.4f}  "
            f"(budget: ${node_budget:.2f}, remaining: ${remaining:.2f})"
        )
    else:
        click.echo(f"  {task_id:<20} ${cost:.4f}")


def print_cost_text(run_id: str, cost_summary: Any, cost_records: Any) -> None:
    """Format cost data as human-readable text."""
    from binex.cli import has_rich

    if has_rich():
        _print_cost_rich(run_id, cost_summary)
    else:
        _print_cost_plain(run_id, cost_summary, cost_records)


def _find_node_budget(cost_records: Any, task_id: str) -> float | None:
    """Find node_budget from cost records for a given task."""
    for r in cost_records:
        if r.task_id == task_id and r.node_budget is not None:
            return float(r.node_budget)
    return None


@cost_group.command("history")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def cost_history_cmd(run_id: str, json_out: bool) -> None:
    """Display chronological cost events for a run."""
    asyncio.run(_cost_history(run_id, json_out))


def _print_history_json(run_id: str, records: Any) -> None:
    """Format cost history as JSON."""
    data = {
        "run_id": run_id,
        "records": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "cost": r.cost,
                "currency": r.currency,
                "source": r.source,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in records
        ],
    }
    click.echo(json.dumps(data, default=str, indent=2))


def _print_history_rich(run_id: str, records: Any) -> None:
    """Render cost history using Rich table."""
    from binex.cli.ui import get_console, make_panel, make_table

    table = make_table(
        ("Time", {"style": "dim", "min_width": 10}),
        ("Node", {"style": "bold", "min_width": 18}),
        ("Cost", {"justify": "right"}),
        ("Source", {"style": "dim"}),
    )
    for r in records:
        ts = r.timestamp.strftime("%H:%M:%S") if r.timestamp else "?"
        table.add_row(ts, r.task_id, f"${r.cost:.4f}", r.source)

    panel = make_panel(
        table, title="Cost History", subtitle=f"run: {run_id}",
    )
    get_console().print(panel)


def _print_history_plain(run_id: str, records: Any) -> None:
    """Render cost history as plain text."""
    click.echo(f"Cost history for {run_id}:\n")
    for r in records:
        ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"{ts}  {r.task_id:<20} ${r.cost:.2f}  ({r.source})")


async def _cost_history(run_id: str, json_out: bool) -> None:
    execution_store, _ = _get_stores()
    try:
        run = await execution_store.get_run(run_id)
        if run is None:
            click.echo(f"Error: Run '{run_id}' not found.", err=True)
            click.echo("Tip: use 'binex explore' to browse available runs.", err=True)
            sys.exit(1)

        records = await execution_store.list_costs(run_id)

        if json_out:
            _print_history_json(run_id, records)
        else:
            from binex.cli import has_rich

            if has_rich():
                _print_history_rich(run_id, records)
            else:
                _print_history_plain(run_id, records)
    finally:
        await execution_store.close()
