"""CLI `binex run` command — execute a workflow."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores import create_artifact_store, create_execution_store
from binex.workflow_spec.loader import load_workflow
from binex.workflow_spec.validator import validate_workflow


@click.command("run")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--var", multiple=True, help="Variable substitution key=value")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def run_cmd(workflow_file: str, var: tuple[str, ...], json_out: bool) -> None:
    """Execute a workflow definition."""
    user_vars = _parse_vars(var)
    spec = load_workflow(workflow_file, user_vars=user_vars)

    errors = validate_workflow(spec)
    if errors:
        for err in errors:
            click.echo(f"Error: {err}", err=True)
        sys.exit(2)

    summary = asyncio.run(_run(spec))

    if json_out:
        click.echo(json.dumps(summary.model_dump(), default=str, indent=2))
    else:
        click.echo(f"Run ID: {summary.run_id}")
        click.echo(f"Workflow: {summary.workflow_name}")
        click.echo(f"Status: {summary.status}")
        click.echo(f"Nodes: {summary.completed_nodes}/{summary.total_nodes} completed")
        if summary.failed_nodes:
            click.echo(f"Failed: {summary.failed_nodes}")

    sys.exit(0 if summary.status == "completed" else 1)


async def _run(spec):
    artifact_store = create_artifact_store(backend="memory")
    execution_store = create_execution_store(backend="memory")

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    # Register a default local echo adapter for local:// agents
    async def _default_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        content = {a.id: a.content for a in inputs} if inputs else {"msg": "no input"}
        return [
            Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )
        ]

    # Auto-register adapters for all agents in the workflow
    for node in spec.nodes.values():
        if node.agent.startswith("local://"):
            orch.dispatcher.register_adapter(
                node.agent, LocalPythonAdapter(handler=_default_handler),
            )

    return await orch.run_workflow(spec)


def _parse_vars(var_tuples: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for v in var_tuples:
        if "=" not in v:
            raise click.BadParameter(f"Invalid var format: {v} (expected key=value)")
        key, value = v.split("=", 1)
        result[key] = value
    return result
