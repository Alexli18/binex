"""CLI `binex replay` command — replay a run from a specific step."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores
from binex.models.execution import RunSummary


@click.command("replay", epilog="""\b
Examples:
  binex replay <run_id> --from step2 --workflow w.yaml
  binex replay <run_id> --from step2 --workflow w.yaml --agent step2=llm://gpt-4o
""")
@click.argument("run_id")
@click.option("--from", "from_step", required=True, help="Re-execute from this step")
@click.option("--workflow", required=True, type=click.Path(exists=True), help="Workflow file")
@click.option("--agent", multiple=True, help="Swap agent: node=agent")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def replay_cmd(
    run_id: str, from_step: str, workflow: str,
    agent: tuple[str, ...], json_out: bool,
) -> None:
    """Replay a run from a specific step or with agent swaps."""
    agent_swaps = _parse_agent_swaps(agent)

    try:
        summary = asyncio.run(_run_replay(run_id, from_step, workflow, agent_swaps))
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_out:
        click.echo(json.dumps(summary.model_dump(), default=str, indent=2))
    else:
        click.echo(f"Replay Run ID: {summary.run_id}")
        click.echo(f"Forked from: {summary.forked_from} at step '{summary.forked_at_step}'")
        click.echo(f"Workflow: {summary.workflow_name}")
        click.echo(f"Status: {summary.status}")
        click.echo(f"Nodes: {summary.completed_nodes}/{summary.total_nodes} completed")
        if summary.failed_nodes:
            click.echo(f"Failed: {summary.failed_nodes}")

    sys.exit(0 if summary.status == "completed" else 1)


async def _run_replay(
    run_id: str,
    from_step: str,
    workflow_path: str,
    agent_swaps: dict[str, str],
) -> RunSummary:
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.runtime.replay import ReplayEngine
    from binex.workflow_spec.loader import load_workflow

    execution_store, artifact_store = get_stores()

    spec = load_workflow(workflow_path)

    engine = ReplayEngine(
        execution_store=execution_store,
        artifact_store=artifact_store,
    )

    register_workflow_adapters(
        engine.dispatcher, spec, agent_swaps=agent_swaps,
    )

    try:
        return await engine.replay(
            original_run_id=run_id,
            workflow=spec,
            from_step=from_step,
            agent_swaps=agent_swaps,
        )
    finally:
        await execution_store.close()


def _parse_agent_swaps(agent_tuples: tuple[str, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for a in agent_tuples:
        if "=" not in a:
            raise click.BadParameter(f"Invalid agent swap format: {a} (expected node=agent)")
        node, agent = a.split("=", 1)
        result[node] = agent
    return result
