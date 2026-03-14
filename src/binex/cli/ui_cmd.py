"""CLI `binex ui` command — launch the Web UI server."""

from __future__ import annotations

import webbrowser

import click
import uvicorn

from binex.ui.server import create_app


@click.command("ui", short_help="Launch the web UI dashboard.")
@click.option("--port", default=8420, type=int, help="Port to serve on.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--dev", is_flag=True, default=False, help="Dev mode — proxy frontend to Vite.")
@click.option(
    "--no-browser", is_flag=True, default=False,
    help="Don't open browser automatically.",
)
def ui_cmd(port: int, host: str, dev: bool, no_browser: bool) -> None:
    """Launch the Binex web UI in a browser."""
    app = create_app()

    if not no_browser:
        url = f"http://{host}:{port}"
        webbrowser.open(url)

    uvicorn.run(app, host=host, port=port, log_level="info", timeout_graceful_shutdown=3)
