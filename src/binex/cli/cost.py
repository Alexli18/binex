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


@click.group("cost")
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
            sys.exit(1)

        cost_summary = await execution_store.get_run_cost_summary(run_id)
        cost_records = await execution_store.list_costs(run_id)

        if json_out:
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
                    }.items() if v is not None
                }
                for r in cost_records
            ]
            click.echo(json.dumps(data, default=str, indent=2))
        else:
            click.echo(f"Run: {run_id}")
            click.echo(f"\nTotal cost: ${cost_summary.total_cost:.2f}")
            if cost_summary.budget is not None:
                click.echo(f"Budget: ${cost_summary.budget:.2f}")
                remaining = cost_summary.remaining_budget or 0.0
                click.echo(f"Remaining: ${remaining:.2f}")
            click.echo("\nNode breakdown:")
            for task_id, cost in cost_summary.node_costs.items():
                if cost > 0:
                    click.echo(f"{task_id:<20} ${cost:.2f}")
    finally:
        await execution_store.close()


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
            click.echo(f"Cost history for {run_id}:\n")
            for r in records:
                ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                click.echo(f"{ts}  {r.task_id:<20} ${r.cost:.2f}  ({r.source})")
    finally:
        await execution_store.close()
