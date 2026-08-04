"""CLI command: ``binex collect`` — start the live OTel collector."""

from __future__ import annotations

import sys
from typing import Any

import click

from binex.cli import get_stores


def _get_stores() -> Any:
    """Create default stores. Extracted for test patching."""
    return get_stores()


@click.command("collect")
@click.option("--port", default=4318, show_default=True, help="Port to listen on.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to.")
@click.option(
    "--quiet-period", default=10, show_default=True,
    help="Seconds of inactivity after root span before finalising a trace.",
)
@click.option(
    "--timeout", default=300, show_default=True,
    help="Hard timeout (seconds) after which a trace is force-finalised.",
)
def collect_cmd(port: int, host: str, quiet_period: int, timeout: int) -> None:
    """Start the live OTel collector server.

    Listens for OTLP/JSON traces on POST /v1/traces and automatically
    converts them to Binex runs once the trace is complete.

    Supports JSON payloads (always) and protobuf (if binex[telemetry] is
    installed).

    \b
    Example:
      binex collect --port 4318
      OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python my_app.py
    """
    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        click.echo(
            "Error: uvicorn is required to run the collector. "
            "Install it with: pip install uvicorn",
            err=True,
        )
        sys.exit(1)

    exec_store, art_store = _get_stores()

    from binex.importers.collector import create_collector_app

    app = create_collector_app(
        exec_store=exec_store,
        art_store=art_store,
        quiet_period=float(quiet_period),
        hard_timeout=float(timeout),
    )

    click.echo(f"Binex OTel Collector listening on http://{host}:{port}")
    click.echo("  POST /v1/traces  — OTLP ingest")
    click.echo("  GET  /health     — liveness probe")
    click.echo(f"  Quiet period: {quiet_period}s  |  Hard timeout: {timeout}s")

    uvicorn.run(app, host=host, port=port, log_level="warning")


__all__ = ["collect_cmd"]
