"""CLI `binex resume` command — continue a failed run from the point of failure."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores
from binex.runtime.resume import ResumeError, ResumeResult


@click.command("resume", epilog="""\b
Examples:
  binex resume <run_id>                 Continue a failed run where it stopped
  binex resume <run_id> --from step3    Force re-run from step3 onward
  binex resume <run_id> --force         Override drift / running-status refusal
""")
@click.argument("run_id")
@click.option(
    "--from", "from_node", default=None,
    help="Force re-execution from this node and everything downstream",
)
@click.option(
    "--force", is_flag=True,
    help="Override topology-drift and running-status refusals",
)
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def resume_cmd(
    run_id: str, from_node: str | None, force: bool, json_out: bool,
) -> None:
    """Resume a failed or interrupted run into a new child run."""
    try:
        result = asyncio.run(_run_resume(run_id, from_node, force))
    except ResumeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    for warning in result.warnings:
        click.echo(f"⚠ {warning}", err=True)

    summary = result.summary
    if json_out:
        data = summary.model_dump()
        data["resumed_nodes"] = result.resumed_nodes
        data["cached_nodes"] = result.cached_nodes
        click.echo(json.dumps(data, default=str, indent=2))
    else:
        click.echo(f"Resume Run ID: {summary.run_id}")
        click.echo(f"Resumed from: {summary.resumed_from}")
        click.echo(f"Workflow: {summary.workflow_name}")
        click.echo(f"Status: {summary.status}")
        click.echo(
            f"Nodes: {summary.completed_nodes}/{summary.total_nodes} completed "
            f"({result.cached_nodes} cached, {result.resumed_nodes} re-run)"
        )
        if summary.failed_nodes:
            click.echo(f"Failed: {summary.failed_nodes}")
        if summary.total_cost > 0:
            click.echo(f"Cost (cumulative): ${summary.total_cost:.4f}")

    sys.exit(0 if summary.status == "completed" else 1)


async def _run_resume(
    run_id: str, from_node: str | None, force: bool,
) -> ResumeResult:
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.plugins import PluginRegistry
    from binex.runtime.resume import ResumeEngine
    from binex.workflow_spec.loader import load_workflow

    execution_store, artifact_store = get_stores()
    try:
        parent = await execution_store.get_run(run_id)
        if parent is None:
            raise ResumeError(f"Run '{run_id}' not found")
        if not parent.workflow_path:
            raise ResumeError(
                f"Run '{run_id}' has no recorded workflow_path; cannot resume."
            )

        spec = load_workflow(parent.workflow_path)

        engine = ResumeEngine(
            execution_store=execution_store,
            artifact_store=artifact_store,
        )

        plugin_registry = PluginRegistry()
        plugin_registry.discover()
        register_workflow_adapters(
            engine.dispatcher, spec, plugin_registry=plugin_registry,
        )

        return await engine.resume(run_id, from_node=from_node, force=force)
    finally:
        await execution_store.close()
