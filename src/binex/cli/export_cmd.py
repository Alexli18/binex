"""CLI `binex export` command — export run data to CSV or JSON."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import click

from binex.cli import get_stores


def _get_stores():
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.command("export")
@click.argument("run_id", required=False, default=None)
@click.option("--last", "last_n", type=int, default=None, help="Export the N most recent runs.")
@click.option(
    "--format", "fmt", type=click.Choice(["csv", "json"]), default="csv",
    help="Output format (csv or json).",
)
@click.option("--include-artifacts", is_flag=True, default=False, help="Include artifact content.")
@click.option(
    "--output", "-o", "output_dir", type=click.Path(), default=None,
    help="Output directory.",
)
def export_cmd(
    run_id: str | None,
    last_n: int | None,
    fmt: str,
    include_artifacts: bool,
    output_dir: str | None,
) -> None:
    """Export run data to CSV or JSON files."""
    if run_id is None and last_n is None:
        click.echo("Error: provide a run_id or --last N", err=True)
        sys.exit(1)
    asyncio.run(_export(run_id, last_n, fmt, include_artifacts, output_dir))


async def _export(
    run_id: str | None,
    last_n: int | None,
    fmt: str,
    include_artifacts: bool,
    output_dir: str | None,
) -> None:
    from binex.export import write_costs_csv, write_json, write_records_csv, write_runs_csv

    execution_store, artifact_store = _get_stores()
    try:
        # Determine which runs to export
        if run_id is not None:
            run = await execution_store.get_run(run_id)
            if run is None:
                click.echo(f"Error: run '{run_id}' not found.", err=True)
                sys.exit(1)
            runs = [run]
        else:
            all_runs = await execution_store.list_runs()
            # Most recent first (by started_at descending)
            all_runs.sort(key=lambda r: r.started_at, reverse=True)
            runs = all_runs[:last_n]

        # Determine output directory
        if output_dir:
            out_path = Path(output_dir)
        elif run_id:
            out_path = Path(f"binex-export-{run_id}")
        else:
            ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            out_path = Path(f"binex-export-{ts}")

        out_path.mkdir(parents=True, exist_ok=True)

        # Gather all records and costs for the runs
        all_records = []
        all_costs = []
        for r in runs:
            records = await execution_store.list_records(r.run_id)
            costs = await execution_store.list_costs(r.run_id)
            all_records.extend(records)
            all_costs.extend(costs)

        # Gather artifacts if requested
        artifacts = None
        if include_artifacts:
            artifacts = []
            for r in runs:
                arts = await artifact_store.list_by_run(r.run_id)
                artifacts.extend(arts)

        # Write output
        if fmt == "csv":
            write_runs_csv(runs, out_path / "runs.csv")
            write_records_csv(all_records, out_path / "records.csv")
            write_costs_csv(all_costs, out_path / "costs.csv")
            if include_artifacts and artifacts:
                # Artifacts always as JSON (non-tabular)
                with open(out_path / "artifacts.json", "w") as f:
                    json.dump(
                        [a.model_dump() for a in artifacts],
                        f, default=str, indent=2,
                    )
        else:
            write_json(
                runs=runs,
                records=all_records,
                costs=all_costs,
                path=out_path / "export.json",
                artifacts=artifacts,
            )

        click.echo(f"Exported {len(runs)} run(s) to {out_path}/")

    finally:
        await execution_store.close()
