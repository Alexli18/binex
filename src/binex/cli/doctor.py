"""CLI command: binex doctor — check system health."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import click
import httpx


def _check_binary(name: str) -> dict:
    """Check if a binary is available on PATH."""
    path = shutil.which(name)
    if path:
        return {"name": name, "status": "ok", "detail": path}
    return {"name": name, "status": "missing", "detail": f"{name} not found on PATH"}


def _check_docker_running() -> dict:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {"name": "Docker Daemon", "status": "ok", "detail": "running"}
        return {"name": "Docker Daemon", "status": "error", "detail": "not running"}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"name": "Docker Daemon", "status": "error", "detail": "cannot connect"}


def _check_http_service(url: str, name: str) -> dict:
    """Check if an HTTP service is reachable."""
    try:
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code == 200:
            return {"name": name, "status": "ok", "detail": url}
        return {
            "name": name,
            "status": "degraded",
            "detail": f"{url} returned {resp.status_code}",
        }
    except httpx.ConnectError:
        return {"name": name, "status": "unreachable", "detail": f"{url} connection refused"}
    except httpx.TimeoutException:
        return {"name": name, "status": "timeout", "detail": f"{url} timed out"}
    except Exception as e:
        return {"name": name, "status": "error", "detail": str(e)}


def _check_store_backend() -> dict:
    """Check if store directory exists."""
    from pathlib import Path

    from binex.settings import Settings

    settings = Settings()
    store_path = Path(settings.store_path)
    if store_path.exists():
        return {"name": "Store Backend", "status": "ok", "detail": str(store_path.resolve())}
    return {
        "name": "Store Backend",
        "status": "not initialized",
        "detail": f"{store_path} does not exist (will be created on first run)",
    }


def run_checks() -> list[dict]:
    """Run all health checks and return results."""
    checks: list[dict] = []

    # Binary checks
    checks.append(_check_binary("docker"))
    checks.append(_check_binary("docker"))  # just one
    checks[1] = _check_docker_running()

    # Service checks
    services = [
        ("http://localhost:11434/api/tags", "Ollama"),
        ("http://localhost:4000/health", "LiteLLM Proxy"),
        ("http://localhost:8000/health", "Registry"),
        ("http://localhost:8001/health", "Planner Agent"),
        ("http://localhost:8002/health", "Researcher Agent"),
        ("http://localhost:8003/health", "Validator Agent"),
        ("http://localhost:8004/health", "Summarizer Agent"),
    ]
    for url, name in services:
        checks.append(_check_http_service(url, name))

    # Store backend
    checks.append(_check_store_backend())

    return checks


STATUS_ICONS = {
    "ok": "✓",
    "missing": "✗",
    "error": "✗",
    "degraded": "⚠",
    "unreachable": "✗",
    "timeout": "⚠",
    "not initialized": "○",
}


@click.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def doctor_cmd(as_json: bool) -> None:
    """Check system health and report status of all components."""
    checks = run_checks()

    if as_json:
        click.echo(json.dumps(checks, indent=2))
    else:
        click.echo("Binex System Health Check\n")
        has_errors = False
        for check in checks:
            icon = STATUS_ICONS.get(check["status"], "?")
            click.echo(f"  {icon} {check['name']}: {check['status']} — {check['detail']}")
            if check["status"] in ("missing", "error", "unreachable"):
                has_errors = True

        click.echo()
        if has_errors:
            click.echo("⚠ Some checks failed. Run 'binex dev' to start services.")
            sys.exit(1)
        else:
            click.echo("✓ All checks passed.")
