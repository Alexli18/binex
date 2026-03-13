"""CLI entry point — top-level `binex` command group."""

from __future__ import annotations

import os

import click
from dotenv import load_dotenv

from binex.cli import BinexGroup
from binex.cli.artifacts import artifacts_cmd
from binex.cli.bisect import bisect_cmd
from binex.cli.cost import cost_group
from binex.cli.debug import debug_cmd
from binex.cli.dev import dev_cmd
from binex.cli.diagnose import diagnose_cmd
from binex.cli.diff import diff_cmd
from binex.cli.doctor import doctor_cmd
from binex.cli.explore import explore_cmd
from binex.cli.export_cmd import export_cmd
from binex.cli.gateway_cmd import gateway
from binex.cli.hello import hello_cmd
from binex.cli.init_cmd import init_cmd
from binex.cli.plugins_cmd import plugins_group
from binex.cli.replay import replay_cmd
from binex.cli.run import cancel_cmd, run_cmd
from binex.cli.scaffold import scaffold_group
from binex.cli.start import start_cmd
from binex.cli.trace import trace_cmd
from binex.cli.validate import validate_cmd

_EPILOG = """\b
Examples:
  binex hello                              Run the built-in demo
  binex run workflow.yaml --var topic=AI   Execute a workflow
  binex debug latest                       Inspect the most recent run
  binex init                               Create a new project

Learn more:
  https://binex.dev/docs
"""


@click.group(cls=BinexGroup, epilog=_EPILOG)
@click.version_option(package_name="binex")
@click.option(
    "--no-color", is_flag=True, default=False,
    help="Disable colored output.",
)
@click.pass_context
def cli(ctx: click.Context, no_color: bool) -> None:
    """Binex — debuggable runtime for A2A agents."""
    if no_color or os.environ.get("NO_COLOR"):
        ctx.color = False


cli.add_command(run_cmd, "run")
cli.add_command(cancel_cmd, "cancel")
cli.add_command(trace_cmd, "trace")
cli.add_command(artifacts_cmd, "artifacts")
cli.add_command(replay_cmd, "replay")
cli.add_command(debug_cmd, "debug")
cli.add_command(diff_cmd, "diff")
cli.add_command(hello_cmd, "hello")
cli.add_command(dev_cmd, "dev")
cli.add_command(doctor_cmd, "doctor")
cli.add_command(validate_cmd, "validate")
cli.add_command(scaffold_group, "scaffold")
cli.add_command(init_cmd, "init")
cli.add_command(start_cmd, "start")
cli.add_command(explore_cmd, "explore")
cli.add_command(cost_group, "cost")
cli.add_command(diagnose_cmd, "diagnose")
cli.add_command(bisect_cmd, "bisect")
cli.add_command(gateway, "gateway")
cli.add_command(plugins_group, "plugins")
cli.add_command(export_cmd, "export")


def main() -> None:
    load_dotenv()
    cli()
