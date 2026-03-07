"""CLI `binex trace` command — inspect execution trace."""

from __future__ import annotations

import asyncio
import json
import sys

import click

from binex.stores import create_artifact_store, create_execution_store
from binex.trace.tracer import generate_timeline, generate_timeline_json


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return create_execution_store(backend="memory"), create_artifact_store(backend="memory")


class TraceGroup(click.Group):
    """Custom group that treats unknown subcommands as run_id for default timeline."""

    def parse_args(self, ctx, args):
        # If first arg is not a known subcommand, treat as `binex trace <run_id>`
        if args and args[0] not in self.commands:
            args = ["timeline"] + args
        return super().parse_args(ctx, args)


@click.group("trace", cls=TraceGroup)
def trace_cmd() -> None:
    """Inspect execution trace for a run."""


@trace_cmd.command("timeline")
@click.argument("run_id")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def trace_timeline_cmd(run_id: str, json_out: bool) -> None:
    """Human-readable timeline of all steps (default)."""
    exec_store, _ = _get_stores()
    if json_out:
        data = asyncio.run(generate_timeline_json(exec_store, run_id))
        click.echo(json.dumps(data, indent=2))
    else:
        output = asyncio.run(generate_timeline(exec_store, run_id))
        click.echo(output)


@trace_cmd.command("node")
@click.argument("run_id")
@click.argument("step")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def trace_node_cmd(run_id: str, step: str, json_out: bool) -> None:
    """Show detailed view of a single execution step."""
    exec_store, _ = _get_stores()
    record = asyncio.run(exec_store.get_step(run_id, step))
    if record is None:
        click.echo(f"Error: Step '{step}' not found in run '{run_id}'.", err=True)
        sys.exit(1)

    if json_out:
        click.echo(json.dumps(record.model_dump(), default=str, indent=2))
    else:
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
def trace_graph_cmd(run_id: str, json_out: bool) -> None:
    """Show ASCII DAG visualization of a run."""
    exec_store, _ = _get_stores()
    records = asyncio.run(exec_store.list_records(run_id))
    if not records:
        click.echo(f"No records found for run '{run_id}'.", err=True)
        sys.exit(1)

    nodes: dict[str, str] = {}
    for rec in records:
        status_icon = "+" if rec.status.value == "completed" else "x"
        nodes[rec.task_id] = f"[{status_icon}] {rec.task_id} ({rec.agent_id})"

    # Infer edges from artifact refs
    output_map: dict[str, str] = {}
    for rec in records:
        for art_ref in rec.output_artifact_refs:
            output_map[art_ref] = rec.task_id

    edge_list: list[tuple[str, str]] = []
    for rec in records:
        for art_ref in rec.input_artifact_refs:
            if art_ref in output_map:
                edge_list.append((output_map[art_ref], rec.task_id))

    if json_out:
        data = {
            "nodes": [
                {"id": rec.task_id, "agent": rec.agent_id, "status": rec.status.value}
                for rec in records
            ],
            "edges": [{"from": src, "to": dst} for src, dst in edge_list],
        }
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo("DAG:")
        rendered: set[str] = set()
        _render_dag(nodes, edge_list, rendered, click.echo)


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
