"""CLI `binex trace` command — inspect execution trace."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.cli import get_stores, has_rich
from binex.trace.tracer import generate_timeline, generate_timeline_json


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


class TraceGroup(click.Group):
    """Custom group that treats unknown subcommands as run_id for default timeline."""

    def parse_args(self, ctx, args):
        # If first arg is not a known subcommand, treat as `binex trace <run_id>`
        if args and args[0] not in self.commands:
            args = ["timeline"] + args
        return super().parse_args(ctx, args)


@click.group("trace", cls=TraceGroup, epilog="""\b
Examples:
  binex trace <run_id>               Show timeline (default)
  binex trace timeline <run_id>      Same as above
  binex trace node <run_id> <step>   Inspect a single step
  binex trace graph <run_id>         Show DAG visualization
""")
def trace_cmd() -> None:
    """Inspect execution trace for a run."""


@trace_cmd.command("timeline")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
def trace_timeline_cmd(run_id: str, json_out: bool, rich_out: bool | None) -> None:
    """Human-readable timeline of all steps (default)."""
    if rich_out is None:
        rich_out = has_rich()
    asyncio.run(_timeline(run_id, json_out, rich_out))


async def _timeline(run_id: str, json_out: bool, rich_out: bool = False) -> None:
    exec_store, _ = _get_stores()
    try:
        if json_out:
            data = await generate_timeline_json(exec_store, run_id)
            click.echo(json.dumps(data, indent=2))
        elif rich_out:
            from binex.trace.trace_rich import format_trace_rich
            await format_trace_rich(exec_store, run_id)
        else:
            output = await generate_timeline(exec_store, run_id)
            click.echo(output)
    finally:
        await exec_store.close()


@trace_cmd.command("node")
@click.argument("run_id")
@click.argument("step")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
def trace_node_cmd(run_id: str, step: str, json_out: bool, rich_out: bool | None) -> None:
    """Show detailed view of a single execution step."""
    if rich_out is None:
        rich_out = has_rich()
    asyncio.run(_node(run_id, step, json_out, rich_out))


async def _node(run_id: str, step: str, json_out: bool, rich_out: bool = False) -> None:
    exec_store, _ = _get_stores()
    try:
        record = await exec_store.get_step(run_id, step)
        if record is None:
            click.echo(f"Error: Step '{step}' not found in run '{run_id}'.", err=True)
            sys.exit(1)

        if json_out:
            click.echo(json.dumps(record.model_dump(), default=str, indent=2))
        elif rich_out:
            from binex.trace.trace_rich import format_trace_node_rich
            await format_trace_node_rich(record)
        else:
            _print_node_plain(record)
    finally:
        await exec_store.close()


def _print_node_plain(record) -> None:
    """Print execution record details in plain text."""
    click.echo(f"Step: {record.task_id}")
    click.echo(f"Agent: {record.agent_id}")
    click.echo(f"Status: {record.status.value}")
    click.echo(f"Latency: {record.latency_ms}ms")
    click.echo(f"Timestamp: {record.timestamp}")
    if record.input_artifact_refs:
        click.echo(f"Inputs: {', '.join(record.input_artifact_refs)}")
    if record.output_artifact_refs:
        click.echo(f"Outputs: {', '.join(record.output_artifact_refs)}")
    if record.error:
        click.echo(f"Error: {record.error}")
    if record.prompt:
        click.echo(f"Prompt: {record.prompt}")
    if record.model:
        click.echo(f"Model: {record.model}")


@trace_cmd.command("graph")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
@click.option("--rich/--no-rich", "rich_out", default=None, help="Rich output (auto-detected)")
def trace_graph_cmd(run_id: str, json_out: bool, rich_out: bool | None) -> None:
    """Show DAG visualization of a run."""
    if rich_out is None:
        rich_out = has_rich()
    asyncio.run(_graph(run_id, json_out, rich_out))


async def _graph(run_id: str, json_out: bool, rich_out: bool = False) -> None:
    exec_store, _ = _get_stores()
    try:
        records = await exec_store.list_records(run_id)
        if not records:
            click.echo(f"No records found for run '{run_id}'.", err=True)
            sys.exit(1)

        nodes, edge_list = _build_graph_from_records(records)

        if json_out:
            data = {
                "nodes": [
                    {"id": rec.task_id, "agent": rec.agent_id, "status": rec.status.value}
                    for rec in records
                ],
                "edges": [{"from": src, "to": dst} for src, dst in edge_list],
            }
            click.echo(json.dumps(data, indent=2))
        elif rich_out:
            from binex.trace.trace_rich import format_trace_graph_rich
            await format_trace_graph_rich(records, nodes, edge_list)
        else:
            click.echo("DAG:")
            _render_dag(nodes, edge_list, set(), click.echo)
    finally:
        await exec_store.close()


def _build_graph_from_records(records) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Build node labels and edge list from execution records."""
    nodes: dict[str, str] = {}
    for rec in records:
        status_icon = "+" if rec.status.value == "completed" else "x"
        nodes[rec.task_id] = f"[{status_icon}] {rec.task_id} ({rec.agent_id})"

    output_map: dict[str, str] = {}
    for rec in records:
        for art_ref in rec.output_artifact_refs:
            output_map[art_ref] = rec.task_id

    edge_list: list[tuple[str, str]] = []
    for rec in records:
        for art_ref in rec.input_artifact_refs:
            if art_ref in output_map:
                edge_list.append((output_map[art_ref], rec.task_id))

    return nodes, edge_list


def _render_dag(
    nodes: dict[str, str],
    edges: list[tuple[str, str]],
    rendered: set[str],
    echo,
) -> None:
    """Simple topological ASCII render."""
    children: dict[str, list[str]] = {n: [] for n in nodes}
    has_parent: set[str] = set()
    for src, dst in edges:
        children.setdefault(src, []).append(dst)
        has_parent.add(dst)

    roots = [n for n in nodes if n not in has_parent]
    if not roots:
        roots = list(nodes.keys())[:1]

    def _print(node: str, prefix: str = "") -> None:
        if node in rendered:
            return
        rendered.add(node)
        echo(f"{prefix}{nodes[node]}")
        for child in children.get(node, []):
            echo(f"{prefix}  |")
            _print(child, prefix + "  ")

    for root in roots:
        _print(root)
