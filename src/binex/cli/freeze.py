"""CLI `binex freeze` — write a pipeline lockfile / check for drift (issue #69)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from binex.workflow_spec.freeze import check_drift, compute_lock, unpinnable_models
from binex.workflow_spec.loader import load_workflow

DEFAULT_LOCK = "binex.lock"


@click.command("freeze", epilog="""\b
Examples:
  binex freeze workflow.yaml                 Write binex.lock
  binex freeze workflow.yaml -o my.lock      Custom lockfile path
  binex freeze workflow.yaml --check         Report drift vs the lockfile
""")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option("-o", "--output", "output", default=DEFAULT_LOCK,
              help=f"Lockfile path (default: {DEFAULT_LOCK})")
@click.option("--check", "check", is_flag=True,
              help="Report drift against the lockfile instead of writing it")
def freeze_cmd(workflow_file: str, output: str, check: bool) -> None:
    """Write a lockfile for a workflow, or check it for drift."""
    spec = load_workflow(workflow_file)

    if check:
        lock_path = Path(output)
        if not lock_path.exists():
            click.echo(f"Error: lockfile '{output}' not found.", err=True)
            sys.exit(1)
        lock = json.loads(lock_path.read_text())
        drift = check_drift(spec, lock)
        if drift:
            click.echo(f"Drift detected vs {output}:", err=True)
            for d in drift:
                click.echo(f"  - {d}", err=True)
            sys.exit(1)
        click.echo(f"No drift — '{spec.name}' matches {output}.")
        return

    lock = compute_lock(spec)
    Path(output).write_text(json.dumps(lock, indent=2) + "\n")
    click.echo(f"Wrote {output} ({len(lock['nodes'])} nodes).")
    unpinned = unpinnable_models(lock)
    if unpinned:
        click.echo(
            f"Note: {len(unpinned)} node(s) use unpinnable model aliases "
            f"({', '.join(sorted(unpinned))}) — the provider can change them "
            "underneath the lock. Use a dated snapshot to pin.",
            err=True,
        )
