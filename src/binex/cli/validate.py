"""CLI `binex validate` command — check a workflow file for errors."""

from __future__ import annotations

import json
import sys

import click

from binex.workflow_spec.loader import load_workflow
from binex.workflow_spec.validator import validate_workflow


def _output_errors(errors: list[str], json_out: bool, *, show_tip: bool = False) -> None:
    """Output validation errors and exit."""
    if json_out:
        click.echo(json.dumps({"valid": False, "errors": errors}, indent=2))
    else:
        for err in errors:
            click.echo(f"Error: {err}", err=True)
        if show_tip:
            click.echo(
                "\nTip: use 'binex scaffold workflow --list-patterns' for valid examples.",
                err=True,
            )
    sys.exit(2)


def _output_success(spec, json_out: bool) -> None:
    """Output validation success summary."""
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
        from binex.cli import has_rich

        if has_rich():
            from rich.text import Text

            from binex.cli.ui import get_console, make_panel

            content = Text()
            content.append(f"Workflow '{spec.name}' is valid\n\n", style="bold green")
            content.append(f"  Nodes:  {node_count}\n")
            content.append(f"  Edges:  {edge_count}\n")
            content.append(f"  Agents: {', '.join(agents)}")
            get_console().print(make_panel(content, title="Validation"))
        else:
            click.echo(f"Workflow '{spec.name}' is valid.")
            click.echo(f"  Nodes:  {node_count}")
            click.echo(f"  Edges:  {edge_count}")
            click.echo(f"  Agents: {', '.join(agents)}")

    sys.exit(0)


@click.command("validate", epilog="""\b
Examples:
  binex validate workflow.yaml          Check for errors
  binex validate workflow.yaml --json   Machine-readable output
""")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def validate_cmd(workflow_file: str, json_out: bool) -> None:
    """Validate a workflow definition (YAML syntax, DAG structure, agent refs)."""
    # Phase 1: load and parse
    try:
        spec = load_workflow(workflow_file)
    except ValueError as exc:
        _output_errors([str(exc)], json_out)

    # Phase 2: structural validation
    errors = validate_workflow(spec)
    if errors:
        _output_errors(errors, json_out, show_tip=True)

    # Phase 3: success summary
    _output_success(spec, json_out)
