"""CLI command: binex hello — run a built-in demo workflow."""

from __future__ import annotations

import asyncio
import json
import sys
import time as _time

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


def _can_use_live() -> bool:
    """Return True when rich live display is available and output is a TTY."""
    from binex.cli import has_rich
    return has_rich() and sys.stderr.isatty()


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

    _print_next_steps(summary)


def _print_next_steps(summary) -> None:
    """Print next-steps guidance, using a rich panel when available."""
    from binex.cli import has_rich

    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        lines = Text()
        lines.append("Next steps:\n\n", style="bold")
        lines.append(f"  binex debug {summary.run_id}", style="cyan")
        lines.append("   \u2014 inspect the run\n")
        lines.append("  binex init", style="cyan")
        lines.append("                       \u2014 create your own project\n")
        lines.append("  binex run examples/simple.yaml", style="cyan")
        lines.append("   \u2014 try a workflow file")

        get_console(stderr=True).print(make_panel(lines, title="Get Started"))
    else:
        click.echo("\nNext steps:", err=True)
        click.echo(
            f"  binex debug {summary.run_id}               "
            "\u2014 inspect the run",
            err=True,
        )
        click.echo(
            "  binex init                       "
            "\u2014 create your own project",
            err=True,
        )
        click.echo(
            "  binex run examples/simple.yaml   "
            "\u2014 try a workflow file",
            err=True,
        )


def _register_hello_handler(orch):
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


async def _run_hello():
    spec = _build_hello_workflow()
    execution_store, artifact_store = _get_stores()

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    node_outputs: dict[str, str] = {}

    use_live = _can_use_live()

    if use_live:
        return await _run_hello_live(orch, spec, execution_store, node_outputs)

    # Plain verbose fallback (used by CliRunner in tests)
    _install_verbose_wrapper(orch, node_outputs)
    _register_hello_handler(orch)

    try:
        summary = await orch.run_workflow(spec)
        return summary, node_outputs
    finally:
        await execution_store.close()


def _install_verbose_wrapper(orch, node_outputs):
    """Monkey-patch orchestrator to print per-node progress (plain text)."""
    original_execute = orch._execute_node
    counter = [0]

    async def _verbose_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0, node_artifacts_history_=None,
    ):
        counter[0] += 1
        total = len(spec_.nodes)
        click.echo(f"\n  [{counter[0]}/{total}] {node_id_} ...", err=True)

        await original_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_,
            node_id_, node_artifacts_, accumulated_cost_, node_artifacts_history_,
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


async def _run_hello_live(orch, spec, execution_store, node_outputs):
    """Run hello workflow with live-updating rich table."""
    from rich.live import Live

    from binex.cli.ui import LiveRunTable, get_console

    nodes_info = [
        {"id": nid, "agent": node.agent, "depends_on": list(node.depends_on)}
        for nid, node in spec.nodes.items()
    ]
    live_table = LiveRunTable(nodes_info)

    original_execute = orch._execute_node

    async def _live_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0, node_artifacts_history_=None,
    ):
        live_table.update_node(node_id_, "running")
        live.update(live_table.build())
        t0 = _time.monotonic()
        try:
            await original_execute(
                spec_, dag_, scheduler_, run_id_, trace_id_,
                node_id_, node_artifacts_, accumulated_cost_, node_artifacts_history_,
            )
            elapsed = _time.monotonic() - t0
            live_table.update_node(
                node_id_, "completed", latency=f"{elapsed:.2f}s",
            )
        except Exception as exc:
            elapsed = _time.monotonic() - t0
            live_table.update_node(
                node_id_, "failed",
                latency=f"{elapsed:.2f}s",
                error=str(exc)[:50],
            )
            raise
        finally:
            if node_id_ in node_artifacts_:
                for art in node_artifacts_[node_id_]:
                    content = art.content
                    if isinstance(content, dict):
                        content = json.dumps(content)
                    node_outputs[node_id_] = content
            live.update(live_table.build())

    orch._execute_node = _live_execute
    _register_hello_handler(orch)

    try:
        with Live(
            live_table.build(),
            console=get_console(stderr=True),
            refresh_per_second=4,
        ) as live:
            summary = await orch.run_workflow(spec)
        return summary, node_outputs
    finally:
        await execution_store.close()
