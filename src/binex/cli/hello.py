"""CLI command: binex hello — run a built-in demo workflow."""

from __future__ import annotations

import asyncio
import json

import click

from binex.adapters.local import LocalPythonAdapter
from binex.cli import get_stores
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _build_hello_workflow() -> WorkflowSpec:
    """Create a simple 2-node demo workflow in-memory."""
    return WorkflowSpec(
        name="hello-world",
        description="Built-in demo workflow",
        nodes={
            "greeter": NodeSpec(
                id="greeter",
                agent="local://echo",
                system_prompt="greet",
                inputs={},
                outputs=["result"],
                depends_on=[],
            ),
            "responder": NodeSpec(
                id="responder",
                agent="local://echo",
                system_prompt="respond",
                inputs={"greeter": "${greeter.result}"},
                outputs=["result"],
                depends_on=["greeter"],
            ),
        },
    )


@click.command("hello")
def hello_cmd() -> None:
    """Run a built-in hello-world demo workflow."""
    click.echo("Running built-in hello-world workflow...", err=True)
    summary, node_outputs = asyncio.run(_run_hello())

    click.echo(
        f"\nRun completed ({summary.completed_nodes}/{summary.total_nodes} nodes)",
        err=True,
    )
    click.echo(f"Run ID: {summary.run_id}", err=True)

    click.echo("\nNext steps:", err=True)
    click.echo(f"  binex debug {summary.run_id}               — inspect the run", err=True)
    click.echo("  binex init                       — create your own project", err=True)
    click.echo("  binex run examples/simple.yaml   — try a workflow file", err=True)


async def _run_hello():
    spec = _build_hello_workflow()
    execution_store, artifact_store = _get_stores()

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    # Track node outputs for display
    node_outputs: dict[str, str] = {}

    # Wrap _execute_node for verbose progress output
    original_execute = orch._execute_node
    counter = [0]

    async def _verbose_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
    ):
        counter[0] += 1
        total = len(spec_.nodes)
        click.echo(f"\n  [{counter[0]}/{total}] {node_id_} ...", err=True)

        await original_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_,
            node_id_, node_artifacts_,
        )

        if node_id_ in node_artifacts_:
            for art in node_artifacts_[node_id_]:
                content = art.content
                if isinstance(content, dict):
                    content = json.dumps(content)
                node_outputs[node_id_] = content
                click.echo(f"  [{node_id_}] -> {art.type}:", err=True)
                click.echo(f"{content}\n", err=True)

    orch._execute_node = _verbose_execute

    # Register the hello-specific echo handler
    async def _hello_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        if task.node_id == "greeter":
            content = "Hello from Binex!"
        else:
            # responder: return JSON of input contents
            content = json.dumps({a.lineage.produced_by: a.content for a in inputs})

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

    orch.dispatcher.register_adapter(
        "local://echo", LocalPythonAdapter(handler=_hello_handler),
    )

    try:
        summary = await orch.run_workflow(spec)
        return summary, node_outputs
    finally:
        await execution_store.close()
