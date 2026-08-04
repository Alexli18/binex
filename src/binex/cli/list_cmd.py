"""CLI `binex list` — discover available workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from binex.workflow_spec.discovery import get_examples_dir, scan_workflow_details


def _find_workflows(directory: Path) -> list[dict[str, Any]]:
    """Scan directory for .yaml/.yml files that look like Binex workflows."""
    return scan_workflow_details(directory)


def _get_examples_dir() -> Path | None:
    """Locate the bundled examples/ directory."""
    return get_examples_dir()


@click.command("list")
@click.option(
    "--json", "as_json", is_flag=True, default=False,
    help="Output as JSON.",
)
def list_cmd(as_json: bool) -> None:
    """List available workflows in the current directory and examples."""
    from binex.cli import has_rich

    cwd = Path.cwd()
    local_workflows = _find_workflows(cwd)

    examples_dir = _get_examples_dir()
    example_workflows = _find_workflows(examples_dir) if examples_dir else []

    if as_json:
        import json

        output = {
            "local": local_workflows,
            "examples": example_workflows,
        }
        click.echo(json.dumps(output, indent=2))
        return

    if has_rich():
        _render_rich(local_workflows, example_workflows)
    else:
        _render_plain(local_workflows, example_workflows)


def _render_rich(local: list[dict[str, Any]], examples: list[dict[str, Any]]) -> None:
    from binex.cli.ui import get_console

    console = get_console()

    if local:
        console.print("\n[bold cyan]Local workflows:[/bold cyan]")
        for wf in local:
            desc = f" — {wf['description']}" if wf["description"] else ""
            console.print(
                f"  [bold]{wf['name']}[/bold] "
                f"[dim]({wf['nodes']} nodes)[/dim]"
                f"[dim]{desc}[/dim]"
            )
            console.print(f"    [dim]{wf['path']}[/dim]")
    else:
        console.print("\n[dim]No workflows found in current directory.[/dim]")

    if examples:
        console.print(f"\n[bold cyan]Examples ({len(examples)}):[/bold cyan]")
        for wf in examples:
            desc = f" — {wf['description']}" if wf["description"] else ""
            console.print(
                f"  [bold]{wf['name']}[/bold] "
                f"[dim]({wf['nodes']} nodes)[/dim]"
                f"[dim]{desc}[/dim]"
            )
            console.print(f"    [dim]{wf['path']}[/dim]")

    console.print()
    if not local:
        console.print("[dim]Tip: run [cyan]binex start[/cyan] to create a new workflow.[/dim]\n")


def _render_plain(local: list[dict[str, Any]], examples: list[dict[str, Any]]) -> None:
    if local:
        click.echo("\nLocal workflows:")
        for wf in local:
            desc = f" — {wf['description']}" if wf["description"] else ""
            click.echo(f"  {wf['name']} ({wf['nodes']} nodes){desc}")
            click.echo(f"    {wf['path']}")
    else:
        click.echo("\nNo workflows found in current directory.")

    if examples:
        click.echo(f"\nExamples ({len(examples)}):")
        for wf in examples:
            desc = f" — {wf['description']}" if wf["description"] else ""
            click.echo(f"  {wf['name']} ({wf['nodes']} nodes){desc}")
            click.echo(f"    {wf['path']}")

    click.echo()
    if not local:
        click.echo("Tip: run 'binex start' to create a new workflow.\n")
