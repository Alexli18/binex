"""CLI `binex init` — deprecated alias for `binex start --quick`."""

from __future__ import annotations

import click


@click.command("init", hidden=True)
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Create a new Binex project (deprecated — use ``binex start``)."""
    click.echo(
        "Warning: 'binex init' is deprecated and will be removed in a future release. "
        "Use 'binex start' (or 'binex start --quick' for minimal setup) instead.",
        err=True,
    )
    from binex.cli.start import start_cmd

    ctx.invoke(start_cmd, quick=True)
