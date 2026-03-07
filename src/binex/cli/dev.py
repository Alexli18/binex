"""CLI command: binex dev — start local development environment."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import click
import httpx


def _find_compose_file() -> Path:
    """Locate docker-compose.yml relative to package root."""
    candidates = [
        Path.cwd() / "docker" / "docker-compose.yml",
        Path(__file__).resolve().parents[3] / "docker" / "docker-compose.yml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise click.ClickException(
        "docker-compose.yml not found. Expected at ./docker/docker-compose.yml"
    )


def _run_compose(compose_file: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command."""
    cmd = ["docker", "compose", "-f", str(compose_file), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def _wait_for_health(url: str, label: str, timeout: int = 60) -> bool:
    """Wait for a service health endpoint to respond."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=5.0)
            if resp.status_code == 200:
                click.echo(f"  ✓ {label} is healthy")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(2)
    click.echo(f"  ✗ {label} failed to start within {timeout}s")
    return False


@click.command("dev")
@click.option("--detach", is_flag=True, help="Run in background")
def dev_cmd(detach: bool) -> None:
    """Start local development environment with Docker Compose."""
    try:
        compose_file = _find_compose_file()
    except click.ClickException:
        click.echo("Error: docker-compose.yml not found at ./docker/docker-compose.yml")
        sys.exit(2)

    click.echo("Starting Binex local development environment...")
    click.echo(f"Using compose file: {compose_file}")

    # Start services
    up_args = ["up"]
    if detach:
        up_args.append("-d")
    up_args.extend(["--build", "--remove-orphans"])

    if detach:
        result = _run_compose(compose_file, *up_args)
        if result.returncode != 0:
            click.echo(f"Error starting services:\n{result.stderr}")
            sys.exit(1)

        click.echo("\nWaiting for services to be healthy...")

        services = [
            ("http://localhost:11434/api/tags", "Ollama"),
            ("http://localhost:4000/health", "LiteLLM Proxy"),
            ("http://localhost:8000/health", "Registry"),
            ("http://localhost:8001/health", "Planner Agent"),
            ("http://localhost:8002/health", "Researcher Agent"),
            ("http://localhost:8003/health", "Validator Agent"),
            ("http://localhost:8004/health", "Summarizer Agent"),
        ]

        all_healthy = True
        for url, label in services:
            if not _wait_for_health(url, label, timeout=120):
                all_healthy = False

        if all_healthy:
            click.echo("\n✓ All services are running. Use 'binex doctor' to verify.")
        else:
            click.echo("\n⚠ Some services failed to start. Run 'binex doctor' for details.")
    else:
        # Foreground mode — exec into docker compose up
        cmd = ["docker", "compose", "-f", str(compose_file), *up_args]
        try:
            subprocess.run(cmd, check=False)
        except KeyboardInterrupt:
            click.echo("\nStopping services...")
            _run_compose(compose_file, "down")
