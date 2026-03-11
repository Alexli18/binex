"""CLI `binex cost` command group — show and history subcommands."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


async def build_cost_data(exec_store, run_id: str):
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
            _print_cost_text(run_id, cost_summary, cost_records)
    finally:
        await execution_store.close()


def _print_cost_json(run_id, cost_summary, cost_records) -> None:
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


def _print_cost_text(run_id, cost_summary, cost_records) -> None:
    """Format cost data as human-readable text."""
    from binex.cli import has_rich

    if has_rich():
        from rich.console import Group
        from rich.text import Text

        from binex.cli.ui import cost_bar, get_console, make_header, make_panel, make_table

        header = make_header(run=run_id)

        # Build cost table
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

        # Summary line
        summary = Text()
        summary.append("Total: ", style="dim")
        summary.append(f"${cost_summary.total_cost:.4f}", style="bold green")
        if cost_summary.budget is not None:
            remaining = cost_summary.remaining_budget or 0.0
            summary.append(f"  ·  Budget: ${cost_summary.budget:.2f}", style="dim")
            summary.append(f"  ·  Remaining: ${remaining:.2f}", style="dim")

        panel = make_panel(
            Group(header, Text(), table, Text(), summary),
            title="Cost",
            subtitle=f"run: {run_id}",
        )
        get_console().print(panel)
    else:
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
            node_budget = _find_node_budget(cost_records, task_id)
            if node_budget is not None:
                remaining = node_budget - cost
                click.echo(
                    f"  {task_id:<20} ${cost:.4f}  "
                    f"(budget: ${node_budget:.2f}, remaining: ${remaining:.2f})"
                )
            else:
                click.echo(f"  {task_id:<20} ${cost:.4f}")


def _find_node_budget(cost_records, task_id: str) -> float | None:
    """Find node_budget from cost records for a given task."""
    for r in cost_records:
        if r.task_id == task_id and r.node_budget is not None:
            return r.node_budget
    return None


@cost_group.command("history")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def cost_history_cmd(run_id: str, json_out: bool) -> None:
    """Display chronological cost events for a run."""
    asyncio.run(_cost_history(run_id, json_out))


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
        else:
            from binex.cli import has_rich

            if has_rich():
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
            else:
                click.echo(f"Cost history for {run_id}:\n")
                for r in records:
                    ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    click.echo(f"{ts}  {r.task_id:<20} ${r.cost:.2f}  ({r.source})")
    finally:
        await execution_store.close()
