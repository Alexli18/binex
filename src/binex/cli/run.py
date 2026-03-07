"""CLI `binex run` and `binex cancel` commands."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.adapters.local import LocalPythonAdapter
from binex.cli import get_stores
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.workflow_spec.loader import load_workflow
from binex.workflow_spec.validator import validate_workflow


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.command("run")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--var", multiple=True, help="Variable substitution key=value")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show artifact contents after each step")
def run_cmd(
    workflow_file: str, var: tuple[str, ...], json_out: bool, verbose: bool,
) -> None:
    """Execute a workflow definition."""
    user_vars = _parse_vars(var)
    spec = load_workflow(workflow_file, user_vars=user_vars)

    errors = validate_workflow(spec)
    if errors:
        for err in errors:
            click.echo(f"Error: {err}", err=True)
        sys.exit(2)

    summary, node_errors, artifacts = asyncio.run(_run(spec, verbose))

    if not json_out:
        for node_id, err in node_errors:
            click.echo(f"  [{node_id}] Error: {err}", err=True)

    if json_out:
        data = summary.model_dump()
        if verbose:
            data["artifacts"] = [
                {"node": a.lineage.produced_by, "type": a.type, "content": a.content}
                for a in artifacts
            ]
        click.echo(json.dumps(data, default=str, indent=2))
    else:
        click.echo(f"Run ID: {summary.run_id}")
        click.echo(f"Workflow: {summary.workflow_name}")
        click.echo(f"Status: {summary.status}")
        click.echo(f"Nodes: {summary.completed_nodes}/{summary.total_nodes} completed")
        if summary.failed_nodes:
            click.echo(f"Failed: {summary.failed_nodes}")

    sys.exit(0 if summary.status == "completed" else 1)


async def _run(spec, verbose: bool = False):
    execution_store, artifact_store = _get_stores()

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    # Verbose progress callback
    all_artifacts: list[Artifact] = []
    if verbose:
        original_execute = orch._execute_node

        async def _verbose_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        ):
            click.echo(f"\n  Running: {node_id_} ...", err=True)
            await original_execute(
                spec_, dag_, scheduler_, run_id_, trace_id_,
                node_id_, node_artifacts_,
            )
            if node_id_ in node_artifacts_:
                for art in node_artifacts_[node_id_]:
                    all_artifacts.append(art)
                    content = art.content
                    if isinstance(content, str) and len(content) > 2000:
                        content = content[:2000] + "..."
                    click.echo(f"  [{node_id_}] -> {art.type}:", err=True)
                    click.echo(f"{content}\n", err=True)

        orch._execute_node = _verbose_execute

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
        agent = node.agent
        if agent in orch.dispatcher._adapters:
            continue
        if agent.startswith("local://"):
            orch.dispatcher.register_adapter(
                agent, LocalPythonAdapter(handler=_default_handler),
            )
        elif agent.startswith("llm://"):
            from binex.adapters.llm import LLMAdapter
            model = agent.removeprefix("llm://")
            orch.dispatcher.register_adapter(agent, LLMAdapter(model=model))

    try:
        summary = await orch.run_workflow(spec)

        # Collect errors from execution records
        errors = []
        records = await execution_store.list_records(summary.run_id)
        for rec in records:
            if rec.error:
                errors.append((rec.task_id, rec.error))

        # Collect all artifacts if not already done via verbose
        if not verbose:
            all_artifacts = await artifact_store.list_by_run(summary.run_id)

        return summary, errors, all_artifacts
    finally:
        await execution_store.close()


def _parse_vars(var_tuples: tuple[str, ...]) -> dict[str, str]:
    result = {}
    for v in var_tuples:
        if "=" not in v:
            raise click.BadParameter(f"Invalid var format: {v} (expected key=value)")
        key, value = v.split("=", 1)
        result[key] = value
    return result


@click.command("cancel")
@click.argument("run_id")
def cancel_cmd(run_id: str) -> None:
    """Cancel a running workflow by run ID."""
    result = asyncio.run(_cancel(run_id))
    if result == "not_found":
        click.echo(f"Error: Run '{run_id}' not found.", err=True)
        sys.exit(1)
    elif result == "not_running":
        click.echo(
            f"Error: Cannot cancel run '{run_id}' — not running.",
            err=True,
        )
        sys.exit(1)
    else:
        click.echo(f"Run '{run_id}' cancelled.")


async def _cancel(run_id: str) -> str:
    store, _ = _get_stores()
    try:
        run = await store.get_run(run_id)
        if run is None:
            return "not_found"
        if run.status != "running":
            return "not_running"
        run.status = "cancelled"
        await store.update_run(run)
        return "ok"
    finally:
        await store.close()
