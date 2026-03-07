"""CLI entry point — top-level `binex` command group."""

from __future__ import annotations

import click

from binex.cli.artifacts import artifacts_cmd
from binex.cli.dev import dev_cmd
from binex.cli.diff import diff_cmd
from binex.cli.doctor import doctor_cmd
from binex.cli.replay import replay_cmd
from binex.cli.run import cancel_cmd, run_cmd
from binex.cli.scaffold import scaffold_group
from binex.cli.trace import trace_cmd
from binex.cli.validate import validate_cmd


@click.group()
@click.version_option(package_name="binex")
def cli() -> None:
    """Binex — debuggable runtime for A2A agents."""


cli.add_command(run_cmd, "run")
cli.add_command(cancel_cmd, "cancel")
cli.add_command(trace_cmd, "trace")
cli.add_command(artifacts_cmd, "artifacts")
cli.add_command(replay_cmd, "replay")
cli.add_command(diff_cmd, "diff")
cli.add_command(dev_cmd, "dev")
cli.add_command(doctor_cmd, "doctor")
cli.add_command(validate_cmd, "validate")
cli.add_command(scaffold_group, "scaffold")


def main() -> None:
    cli()
