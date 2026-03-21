"""CLI command: binex hello — run a built-in demo workflow."""

from __future__ import annotations

import asyncio
import json

import click

from typing import Any

from binex.adapters.local import LocalPythonAdapter
from binex.cli import get_stores
from binex.cli.run_progress import can_use_live, install_live_wrapper, install_verbose_wrapper
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator


def _get_stores() -> Any:
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
    )
    click.echo(f"Run ID: {summary.run_id}")

    _print_next_steps(summary)


def _print_next_steps(summary: Any) -> None:
    """Print next-steps guidance, using a rich panel when available."""
    from binex.cli import has_rich

    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        lines = Text()
        lines.append("Next steps:\n\n", style="bold")
        lines.append(f"  binex debug {summary.run_id}", style="cyan")
        lines.append("   \u2014 inspect the run\n")
        lines.append("  binex start", style="cyan")
        lines.append("                      \u2014 create your own project\n")
        lines.append("  binex run examples/simple.yaml", style="cyan")
        lines.append("   \u2014 try a workflow file")

        get_console(stderr=False).print(make_panel(lines, title="Get Started"))
    else:
        click.echo("\nNext steps:")
        click.echo(
            f"  binex debug {summary.run_id}               "
            "\u2014 inspect the run",
        )
        click.echo(
            "  binex start                      "
            "\u2014 create your own project",
        )
        click.echo(
            "  binex run examples/simple.yaml   "
            "\u2014 try a workflow file",
        )


def _register_hello_handler(orch: Any) -> None:
    """Register the hello-specific echo handler on the orchestrator."""

    async def _hello_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        if task.node_id == "greeter":
            content = "Hello from Binex!"
        else:
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


async def _run_hello() -> tuple[Any, dict[str, str]]:
    spec = _build_hello_workflow()
    execution_store, artifact_store = _get_stores()

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    node_outputs: dict[str, str] = {}

    use_live = can_use_live()

    if use_live:
        return await _run_hello_live(orch, spec, execution_store, node_outputs)

    # Plain verbose fallback (used by CliRunner in tests)
    install_verbose_wrapper(
        orch,
        on_node_done=lambda nid, na: _collect_hello_artifacts(nid, na, node_outputs),
    )
    _register_hello_handler(orch)

    try:
        summary = await orch.run_workflow(spec)
        return summary, node_outputs
    finally:
        await execution_store.close()


def _collect_hello_artifacts(node_id: str, node_artifacts: dict[str, Any], node_outputs: dict[str, str]) -> None:
    """Collect hello artifacts into node_outputs dict with verbose printing."""
    if node_id not in node_artifacts:
        return
    for art in node_artifacts[node_id]:
        content = art.content
        if isinstance(content, dict):
            content = json.dumps(content)
        node_outputs[node_id] = content
        click.echo(f"  [{node_id}] -> {art.type}:", err=True)
        click.echo(f"{content}\n", err=True)


async def _run_hello_live(orch: Any, spec: Any, execution_store: Any, node_outputs: dict[str, str]) -> tuple[Any, dict[str, str]]:
    """Run hello workflow with live-updating rich table."""
    from rich.live import Live

    from binex.cli.ui import LiveRunTable, get_console

    nodes_info = [
        {"id": nid, "agent": node.agent, "depends_on": list(node.depends_on)}
        for nid, node in spec.nodes.items()
    ]
    live_table = LiveRunTable(nodes_info)

    def _collect(node_id: str, node_artifacts_: dict[str, Any]) -> None:
        if node_id in node_artifacts_:
            for art in node_artifacts_[node_id]:
                content = art.content
                if isinstance(content, dict):
                    content = json.dumps(content)
                node_outputs[node_id] = content

    _register_hello_handler(orch)

    try:
        with Live(
            live_table.build(),
            console=get_console(stderr=True),
            refresh_per_second=4,
        ) as live:
            install_live_wrapper(orch, live_table, live, on_node_done=_collect)
            summary = await orch.run_workflow(spec)
        return summary, node_outputs
    finally:
        await execution_store.close()
