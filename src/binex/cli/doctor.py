"""CLI command: binex doctor — check system health."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any

import click
import httpx


def _check_binary(name: str) -> dict[str, Any]:
    """Check if a binary is available on PATH."""
    path = shutil.which(name)
    if path:
        return {"name": name, "status": "ok", "detail": path}
    return {"name": name, "status": "missing", "detail": f"{name} not found on PATH"}


def _check_docker_running() -> dict[str, Any]:
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


def _check_http_service(url: str, name: str) -> dict[str, Any]:
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


def _check_store_backend() -> dict[str, Any]:
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


def run_checks() -> list[dict[str, Any]]:
    """Run all health checks and return results.

    Checks are split into 'required' (core Binex) and 'optional'
    (infrastructure that only matters when you use those features).
    Optional check failures don't cause exit code 1.
    """
    checks: list[dict[str, Any]] = []

    # Required: Store backend (always needed)
    checks.append({**_check_store_backend(), "required": True})

    # Optional: Docker (only for `binex dev`)
    checks.append({**_check_binary("docker"), "required": False})
    checks.append({**_check_docker_running(), "required": False})

    # Optional: Services (only when configured)
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
        checks.append({**_check_http_service(url, name), "required": False})

    return checks


def _normalize_status(status: str) -> str:
    """Normalize status strings for ui.py lookup (spaces → underscores)."""
    return status.replace(" ", "_")


def _doctor_rich_output(checks: list[dict[str, Any]]) -> None:
    """Render doctor checks using Rich panels and tables."""
    from rich.console import Group
    from rich.text import Text

    from binex.cli.ui import get_console, make_panel, make_table, status_text

    table = make_table(
        ("Check", {"style": "bold", "min_width": 18}),
        ("Detail", {"min_width": 12}),
        ("Status", {"min_width": 10}),
    )
    for check in checks:
        table.add_row(
            check["name"],
            check["detail"],
            status_text(_normalize_status(check["status"])),
        )

    healthy = sum(1 for c in checks if c["status"] == "ok")
    issues = len(checks) - healthy

    footer = Text("  ")
    footer.append(f"{healthy} healthy", style="green")
    if issues:
        footer.append("  ·  ", style="dim")
        footer.append(f"{issues} issues", style="yellow")

    panel = make_panel(
        Group(table, Text(), footer),
        title="System Health",
    )
    get_console().print(panel)


def _doctor_plain_output(checks: list[dict[str, Any]], has_errors: bool) -> None:
    """Render doctor checks as plain text."""
    from binex.cli.ui import plain_status_icon

    click.echo("Binex System Health Check\n")
    for check in checks:
        icon = plain_status_icon(_normalize_status(check["status"]))
        optional = "" if check.get("required", True) else " (optional)"
        click.echo(
            f"  {icon} {check['name']}{optional}: {check['status']}"
            f" — {check['detail']}"
        )
    click.echo()
    if has_errors:
        click.echo("Some checks failed. Run 'binex dev' to start services.")
    else:
        click.echo("All checks passed.")


@click.command("doctor", epilog="""\b
Examples:
  binex doctor            Check all components
  binex doctor --json     Machine-readable output
""")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def doctor_cmd(json_out: bool) -> None:
    """Check system health and report status of all components."""
    checks = run_checks()

    if json_out:
        click.echo(json.dumps(checks, indent=2))
    else:
        has_required_errors = any(
            c.get("required", True) and c["status"] in ("missing", "error", "unreachable")
            for c in checks
        )

        from binex.cli import has_rich as _has_rich

        if _has_rich():
            _doctor_rich_output(checks)
        else:
            _doctor_plain_output(checks, has_required_errors)

        if has_required_errors:
            sys.exit(1)
