"""CLI `binex replay` command — replay a run from a specific step."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from binex.cli import get_stores
from binex.models.execution import RunSummary


@click.command("replay", epilog="""\b
Examples:
  binex replay <run_id> --from step2 --workflow w.yaml
  binex replay <run_id> --from step2 --workflow w.yaml --agent step2=llm://gpt-4o
  binex replay <run_id> --call call_002 --model gpt-4o   (observed-run call replay)
""")
@click.argument("run_id")
@click.option("--from", "from_step", default=None, help="Re-execute from this step")
@click.option("--call", "call_id", default=None,
              help="Replay a single captured LLM call from an observed run")
@click.option("--model", "model", default=None,
              help="Swap the model for --call replay")
@click.option("--prompt-file", "prompt_file", type=click.Path(exists=True),
              default=None, help="Replace the call's user prompt with this file")
@click.option("--mock-response", "mock_response", default=None,
              help="Use a canned response instead of a real call (offline verify)")
@click.option(
    "--workflow", required=False, type=click.Path(exists=True),
    default=None, help="Workflow file (resolved from run metadata if omitted)",
)
@click.option("--agent", multiple=True, help="Swap agent: node=agent")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def replay_cmd(
    run_id: str, from_step: str | None, call_id: str | None,
    model: str | None, prompt_file: str | None, mock_response: str | None,
    workflow: str | None, agent: tuple[str, ...], json_out: bool,
) -> None:
    """Replay a run from a step, or a single captured call from an observed run."""
    if call_id is not None:
        _replay_single_call(
            run_id, call_id, model, prompt_file, mock_response, json_out,
        )
        return
    if from_step is None:
        click.echo("Error: provide --from <step> or --call <call-id>.", err=True)
        sys.exit(2)
    if workflow is None:
        workflow = asyncio.run(_resolve_workflow_from_run(run_id))
        if workflow is None:
            click.echo(
                f"Error: Could not determine workflow path from run '{run_id}' metadata. "
                "Please provide --workflow explicitly.",
                err=True,
            )
            sys.exit(1)

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


def _replay_single_call(
    run_id: str, call_id: str, model: str | None,
    prompt_file: str | None, mock_response: str | None, json_out: bool,
) -> None:
    """Replay a single captured LLM call from an observed run (#74)."""
    from binex.replay_call import ReplayError, replay_call

    prompt = None
    if prompt_file is not None:
        from pathlib import Path
        prompt = Path(prompt_file).read_text(encoding="utf-8")

    try:
        result = asyncio.run(replay_call(
            run_id, call_id, model=model, prompt=prompt,
            mock_response=mock_response,
        ))
    except ReplayError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if json_out:
        click.echo(json.dumps({
            "run_id": result.run_id, "call_id": result.call_id,
            "original_model": result.original_model,
            "replay_model": result.replay_model,
            "original_response": result.original_response,
            "replay_response": result.replay_response,
            "changed": result.changed,
            "cost": result.cost,
            "tool_requests": [
                {"name": t.name, "arguments": t.arguments}
                for t in result.tool_requests
            ],
        }, default=str, indent=2))
    else:
        _print_call_replay(result)

    sys.exit(0)


def _print_call_replay(r: Any) -> None:
    click.echo(f"Replay of {r.call_id} in {r.run_id}")
    model_line = r.original_model
    if r.replay_model != r.original_model:
        model_line = f"{r.original_model} -> {r.replay_model}"
    click.echo(f"Model: {model_line}")
    if r.cost is not None:
        click.echo(f"Replay cost: ${r.cost:.4f} (experimentation, excluded from run total)")
    click.echo(f"\n--- original ---\n{r.original_response}")
    click.echo(f"\n+++ replay +++\n{r.replay_response}")
    if r.tool_requests:
        click.echo("\nReplay requested tool calls (NOT executed):")
        for t in r.tool_requests:
            click.echo(f"  - {t.name}({t.arguments})")
    verdict = "CHANGED" if r.changed else "identical"
    click.echo(f"\nResult: {verdict}")


async def _resolve_workflow_from_run(run_id: str) -> str | None:
    """Look up the workflow path from the run's stored metadata."""
    execution_store, _ = get_stores()
    try:
        run = await execution_store.get_run(run_id)
        if run is None:
            return None
        if run.workflow_path:
            return run.workflow_path
        return None
    finally:
        await execution_store.close()


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

    from binex.plugins import PluginRegistry

    plugin_registry = PluginRegistry()
    plugin_registry.discover()

    register_workflow_adapters(
        engine.dispatcher, spec, agent_swaps=agent_swaps,
        plugin_registry=plugin_registry,
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
