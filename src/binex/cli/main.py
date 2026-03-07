"""CLI entry point — top-level `binex` command group."""

from __future__ import annotations

import click

from binex.cli.run import run_cmd


@click.group()
@click.version_option(package_name="binex")
def cli() -> None:
    """Binex — debuggable runtime for A2A agents."""


cli.add_command(run_cmd, "run")


def main() -> None:
    cli()
