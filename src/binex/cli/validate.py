"""CLI `binex validate` command — check a workflow file for errors."""

from __future__ import annotations

import json
import sys

import click

from binex.workflow_spec.loader import load_workflow
from binex.workflow_spec.validator import validate_workflow


@click.command("validate")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def validate_cmd(workflow_file: str, json_out: bool) -> None:
    """Validate a workflow definition (YAML syntax, DAG structure, agent refs)."""
    # Phase 1: load and parse
    try:
        spec = load_workflow(workflow_file)
    except ValueError as exc:
        errors = [str(exc)]
        if json_out:
            click.echo(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            click.echo(f"Error: {errors[0]}", err=True)
        sys.exit(2)

    # Phase 2: structural validation
    errors = validate_workflow(spec)
    if errors:
        if json_out:
            click.echo(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            for err in errors:
                click.echo(f"Error: {err}", err=True)
        sys.exit(2)

    # Phase 3: success summary
    node_count = len(spec.nodes)
    edge_count = sum(len(n.depends_on) for n in spec.nodes.values())
    agents = sorted({n.agent for n in spec.nodes.values()})

    if json_out:
        click.echo(json.dumps({
            "valid": True,
            "node_count": node_count,
            "edge_count": edge_count,
            "agents": agents,
        }, indent=2))
    else:
        click.echo(f"Workflow '{spec.name}' is valid.")
        click.echo(f"  Nodes:  {node_count}")
        click.echo(f"  Edges:  {edge_count}")
        click.echo(f"  Agents: {', '.join(agents)}")

    sys.exit(0)
