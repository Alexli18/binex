"""CLI `binex run` and `binex cancel` commands."""

from __future__ import annotations

import asyncio
import json
import sys
import time as _time

import click

from binex.cli import get_stores, render_terminal_artifacts
from binex.cli.adapter_registry import register_workflow_adapters
from binex.models.artifact import Artifact
from binex.runtime.orchestrator import Orchestrator
from binex.workflow_spec.loader import load_workflow
from binex.workflow_spec.validator import validate_workflow

VERBOSE_CONTENT_MAX_LEN = 2000


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


def _can_use_live() -> bool:
    """Return True when rich live display is available and output is a TTY."""
    from binex.cli import has_rich
    return has_rich() and sys.stderr.isatty()


@click.command("run", epilog="""\b
Examples:
  binex run workflow.yaml                       Run a workflow
  binex run workflow.yaml --var topic="AI"      Pass variables
  binex run workflow.yaml -v                    Verbose per-node output
  binex run workflow.yaml --json                Machine-readable output
""")
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

    # Identify terminal nodes (no downstream dependents)
    all_deps = {dep for node in spec.nodes.values() for dep in node.depends_on}
    terminal_nodes = [nid for nid in spec.nodes if nid not in all_deps]

    if json_out:
        _print_json_output(summary, spec, artifacts, terminal_nodes, verbose)
    else:
        for node_id, err in node_errors:
            click.echo(f"  [{node_id}] Error: {err}", err=True)
        _print_text_output(summary, spec, artifacts, terminal_nodes)

    sys.exit(0 if summary.status == "completed" else 1)


def _print_json_output(summary, spec, artifacts, terminal_nodes, verbose):
    """Format and print JSON run output."""
    data = summary.model_dump()
    if verbose:
        data["artifacts"] = [
            {"node": a.lineage.produced_by, "type": a.type, "content": a.content}
            for a in artifacts
        ]
    data["output"] = {
        a.lineage.produced_by: a.content
        for a in artifacts
        if a.lineage.produced_by in terminal_nodes
    }
    if spec.budget:
        data["budget"] = spec.budget.max_cost
        data["remaining_budget"] = spec.budget.max_cost - summary.total_cost
    click.echo(json.dumps(data, default=str, indent=2))


def _print_text_output(summary, spec, artifacts, terminal_nodes):
    """Format and print human-readable run output."""
    from binex.cli import has_rich

    if has_rich():
        _print_rich_output(summary, spec, artifacts, terminal_nodes)
        return

    # Plain-text fallback (also used by CliRunner in tests)
    click.echo(f"Run ID: {summary.run_id}")
    click.echo(f"Workflow: {summary.workflow_name}")
    click.echo(f"Status: {summary.status}")
    click.echo(f"Nodes: {summary.completed_nodes}/{summary.total_nodes} completed")
    if summary.failed_nodes:
        click.echo(f"Failed: {summary.failed_nodes}")

    if summary.total_cost > 0:
        click.echo(f"Cost: ${summary.total_cost:.2f}")
    if spec.budget:
        remaining = spec.budget.max_cost - summary.total_cost
        click.echo(f"Budget: ${spec.budget.max_cost:.2f} (remaining: ${remaining:.2f})")
    if summary.status == "over_budget" and spec.budget:
        click.echo("Budget exceeded \u2014 run stopped")
        click.echo(
            f"Spent: ${summary.total_cost:.2f} / Budget: ${spec.budget.max_cost:.2f}"
        )

    if summary.status == "completed" and artifacts:
        render_terminal_artifacts(artifacts, terminal_nodes)

    if summary.status != "completed":
        click.echo(
            f"\nTip: run 'binex debug {summary.run_id}' for full details",
            err=True,
        )


def _print_rich_output(summary, spec, artifacts, terminal_nodes):
    """Print styled run output using rich panels."""
    from rich.console import Group
    from rich.text import Text

    from binex.cli.ui import get_console, make_header, make_panel, status_text

    header = make_header(
        workflow=summary.workflow_name,
        run_id=summary.run_id,
    )

    status_line = Text()
    status_line.append("Status: ", style="dim")
    status_line.append_text(status_text(summary.status))
    status_line.append(
        f"  ({summary.completed_nodes}/{summary.total_nodes} nodes)", style="dim",
    )

    parts: list[Text] = [header, Text(), status_line]

    if summary.total_cost > 0:
        cost_line = Text()
        cost_line.append("Cost: ", style="dim")
        cost_line.append(f"${summary.total_cost:.4f}", style="bold")
        parts.append(cost_line)

    if spec.budget:
        remaining = spec.budget.max_cost - summary.total_cost
        budget_line = Text()
        budget_line.append("Budget: ", style="dim")
        budget_line.append(f"${spec.budget.max_cost:.2f}", style="bold")
        budget_line.append(f" (remaining: ${remaining:.2f})", style="dim")
        parts.append(budget_line)

    if summary.status == "over_budget":
        parts.append(Text("Budget exceeded \u2014 run stopped", style="red bold"))

    get_console().print(make_panel(Group(*parts), title="Run Complete"))

    if summary.status == "completed" and artifacts:
        render_terminal_artifacts(artifacts, terminal_nodes)

    if summary.status != "completed":
        click.echo(
            f"\nTip: run 'binex debug {summary.run_id}' for full details",
            err=True,
        )


async def _run(spec, verbose: bool = False):
    execution_store, artifact_store = _get_stores()

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    all_artifacts: list[Artifact] = []

    # Determine output mode: live table (TTY + rich), plain verbose, or quiet
    use_live = verbose and _can_use_live()

    if use_live:
        return await _run_with_live(
            orch, spec, execution_store, artifact_store, all_artifacts,
        )

    if verbose:
        _install_verbose_wrapper(orch, all_artifacts)

    register_workflow_adapters(orch.dispatcher, spec)

    try:
        summary = await orch.run_workflow(spec)

        errors = _collect_errors(await execution_store.list_records(summary.run_id))

        if verbose:
            _show_skipped_nodes(spec, summary, await execution_store.list_records(summary.run_id))
        else:
            all_artifacts = await artifact_store.list_by_run(summary.run_id)

        return summary, errors, all_artifacts
    finally:
        await execution_store.close()


async def _run_with_live(orch, spec, execution_store, artifact_store, all_artifacts):
    """Run workflow with a live-updating rich table."""
    from rich.live import Live

    from binex.cli.ui import LiveRunTable, get_console

    nodes_info = [
        {"id": nid, "agent": node.agent, "depends_on": list(node.depends_on)}
        for nid, node in spec.nodes.items()
    ]
    live_table = LiveRunTable(nodes_info)

    register_workflow_adapters(orch.dispatcher, spec)

    try:
        with Live(
            live_table.build(),
            console=get_console(stderr=True),
            refresh_per_second=4,
        ) as live:
            _install_live_wrapper(orch, live_table, live, all_artifacts)
            summary = await orch.run_workflow(spec)

        errors = _collect_errors(
            await execution_store.list_records(summary.run_id),
        )
        _show_skipped_nodes(
            spec, summary,
            await execution_store.list_records(summary.run_id),
        )
        return summary, errors, all_artifacts
    finally:
        await execution_store.close()


def _install_live_wrapper(orch, live_table, live, all_artifacts):
    """Monkey-patch orchestrator to update LiveRunTable on each node."""
    original_execute = orch._execute_node

    async def _live_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0,
    ):
        live_table.update_node(node_id_, "running")
        live.update(live_table.build())
        t0 = _time.monotonic()
        try:
            await original_execute(
                spec_, dag_, scheduler_, run_id_, trace_id_,
                node_id_, node_artifacts_, accumulated_cost_,
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
                    all_artifacts.append(art)
            live.update(live_table.build())

    orch._execute_node = _live_execute


def _install_verbose_wrapper(orch: Orchestrator, all_artifacts: list[Artifact]) -> None:
    """Monkey-patch orchestrator to print progress for each node execution."""
    original_execute = orch._execute_node
    counter = [0]

    async def _verbose_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0,
    ):
        counter[0] += 1
        total = len(spec_.nodes)
        click.echo(f"\n  [{counter[0]}/{total}] {node_id_} ...", err=True)

        node_spec = spec_.nodes.get(node_id_)
        if node_spec and node_spec.depends_on:
            for dep in node_spec.depends_on:
                click.echo(f"        <- {dep}", err=True)

        await original_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_,
            node_id_, node_artifacts_, accumulated_cost_,
        )
        if node_id_ in node_artifacts_:
            for art in node_artifacts_[node_id_]:
                all_artifacts.append(art)
                content = art.content
                if isinstance(content, str) and len(content) > VERBOSE_CONTENT_MAX_LEN:
                    content = content[:VERBOSE_CONTENT_MAX_LEN] + "..."
                click.echo(f"  [{node_id_}] -> {art.type}:", err=True)
                click.echo(f"{content}\n", err=True)

    orch._execute_node = _verbose_execute


def _collect_errors(records) -> list[tuple[str, str]]:
    """Extract (task_id, error) pairs from execution records."""
    return [(rec.task_id, rec.error) for rec in records if rec.error]


def _show_skipped_nodes(spec, summary, records) -> None:
    """Print skipped node names in verbose mode."""
    skipped = summary.total_nodes - summary.completed_nodes - summary.failed_nodes
    if skipped > 0:
        executed_ids = {rec.task_id for rec in records}
        for node_id in spec.nodes:
            if node_id not in executed_ids:
                click.echo(f"  [skipped] {node_id}", err=True)


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
