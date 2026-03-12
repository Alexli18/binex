"""Rich output helpers for the start wizard."""

from __future__ import annotations

import sys

import click


def has_rich() -> bool:
    """Proxy to binex.cli.start.has_rich for test-patchability."""
    return sys.modules["binex.cli.start"].has_rich()


def _print_banner() -> None:
    """Print a welcome banner."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        title = Text()
        title.append("Welcome to ", style="bold")
        title.append("Binex", style="bold cyan")
        title.append("!", style="bold")
        subtitle = Text("Let's set up your agent network.", style="dim")
        content = Text.assemble(title, "\n", subtitle)
        console.print()
        console.print(make_panel(content))
        console.print()
    else:
        click.echo("\nWelcome to Binex! Let's set up your agent network.\n")


def _print_step(step: int, total: int, label: str) -> None:
    """Print a step header."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        header = Text()
        header.append(f"Step {step} of {total}", style="bold cyan")
        header.append(f" \u00b7 {label}", style="bold")
        console.print(header)
    else:
        click.echo(f"\nStep {step} of {total} \u00b7 {label}", err=True)


def _print_confirm(message: str) -> None:
    """Print a confirmation/success message."""
    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(f"  [green]\u2713[/green] {message}")
    else:
        click.echo(f"  \u2713 {message}", err=True)


def _print_dsl_preview(dsl: str) -> None:
    """Print a visual preview of the workflow DAG."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        preview = Text()
        preview.append("  Pipeline: ", style="dim")
        # Color node names cyan and arrows dim
        parts = dsl.replace(",", " ,").split()
        for part in parts:
            part_stripped = part.strip()
            if part_stripped == "->":
                preview.append(" \u2192 ", style="dim")
            elif part_stripped == ",":
                preview.append(", ", style="dim")
            else:
                preview.append(part_stripped, style="bold magenta")
        console.print(preview)
        console.print()
    else:
        click.echo(f"  Pipeline: {dsl}\n", err=True)


def _print_file_created(filename: str) -> None:
    """Print a file creation confirmation."""
    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(f"  [green]\u2713[/green] [bold]{filename}[/bold]")
    else:
        click.echo(f"  \u2713 {filename}", err=True)


def _print_done_panel(project_name: str) -> None:
    """Print a completion panel with next steps."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        content = Text()
        content.append(f"Project saved in ./{project_name}/\n\n", style="bold green")
        content.append("Next steps:\n", style="bold")
        content.append(f"  cd {project_name}\n", style="cyan")
        content.append("  binex run workflow.yaml", style="cyan")
        content.append("    \u2014 run your workflow\n", style="dim")
        content.append("  code workflow.yaml", style="cyan")
        content.append("         \u2014 edit your workflow", style="dim")
        console.print()
        console.print(make_panel(content, title="Done!"))
    else:
        click.echo(f"\nDone! Your project is saved in ./{project_name}/\n")
        click.echo("Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  binex run workflow.yaml                \u2014 run your workflow")
        click.echo("  code workflow.yaml                     \u2014 edit your workflow")


def _preview_yaml(yaml_content: str) -> None:
    """Display YAML with syntax highlighting if Rich is available."""
    if has_rich():
        from rich.syntax import Syntax

        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=False)
        console.print()
        console.print(make_panel(syntax, title="Workflow Preview"))
        console.print()
    else:
        click.echo("\n--- Workflow Preview ---")
        click.echo(yaml_content)
        click.echo("--- End Preview ---\n")
