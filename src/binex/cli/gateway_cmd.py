"""CLI commands for the A2A Gateway — start, status, agents."""

from __future__ import annotations

import json
import sys

import click


def _import_httpx():
    """Lazy import httpx. Extracted for test patching."""
    import httpx
    return httpx


def _import_uvicorn():
    """Lazy import uvicorn. Extracted for test patching."""
    import uvicorn
    return uvicorn


@click.group("gateway", invoke_without_command=True)
@click.option(
    "--config", "config_path", type=click.Path(), default=None,
    help="Path to gateway.yaml config file.",
)
@click.option("--host", default=None, help="Override bind host.")
@click.option("--port", default=None, type=int, help="Override bind port.")
@click.pass_context
def gateway(
    ctx: click.Context, config_path: str | None,
    host: str | None, port: int | None,
) -> None:
    """A2A Gateway — start server, check status, list agents."""
    if ctx.invoked_subcommand is not None:
        return

    # Default command: start the gateway server
    _start_server(config_path, host, port)


def _start_server(config_path: str | None, host: str | None, port: int | None) -> None:
    """Load config and start the FastAPI gateway server via uvicorn."""
    from binex.gateway.config import load_gateway_config

    config = load_gateway_config(config_path)
    if config is None:
        click.echo(
            "Error: No gateway config found. "
            "Provide --config or create gateway.yaml.",
            err=True,
        )
        sys.exit(1)

    # Apply CLI overrides
    bind_host = host or config.host
    bind_port = port or config.port

    # Auth info
    if config.auth is not None:
        auth_info = f"{config.auth.type} ({len(config.auth.keys)} keys configured)"
    else:
        auth_info = "disabled"

    agent_count = len(config.agents)
    health_interval = config.health.interval_s

    click.echo(f"A2A Gateway starting on {bind_host}:{bind_port}")
    click.echo(f"  Auth: {auth_info}")
    click.echo(f"  Agents: {agent_count} registered")
    click.echo(f"  Health check: every {health_interval}s")

    # Lazy import to avoid pulling in fastapi/uvicorn at CLI load time
    uvicorn = _import_uvicorn()
    app = create_app(config)
    uvicorn.run(app, host=bind_host, port=bind_port)


def create_app(config):
    """Lazy wrapper for gateway app creation. Extracted for test patching."""
    from binex.gateway.app import create_app as _create_app
    return _create_app(config)


@gateway.command("status")
@click.option(
    "--gateway", "gateway_url", default="http://localhost:8420",
    help="Gateway URL to query.",
)
@click.option("--json", "json_out", is_flag=True, help="Output as JSON.")
def status_cmd(gateway_url: str, json_out: bool) -> None:
    """Check gateway health status."""
    httpx = _import_httpx()

    try:
        response = httpx.get(f"{gateway_url}/health", timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception:
        click.echo(f"Error: Cannot connect to gateway at {gateway_url}", err=True)
        sys.exit(1)

    if json_out:
        output = {
            "gateway": gateway_url,
            "status": data.get("status", "unknown"),
            "agents_total": data.get("agents_total", 0),
            "agents_alive": data.get("agents_alive", 0),
            "agents_degraded": data.get("agents_degraded", 0),
            "agents_down": data.get("agents_down", 0),
        }
        click.echo(json.dumps(output, indent=2))
    else:
        status = data.get("status", "unknown")
        total = data.get("agents_total", 0)
        alive = data.get("agents_alive", 0)
        degraded = data.get("agents_degraded", 0)
        down = data.get("agents_down", 0)
        click.echo(f"Gateway: {gateway_url}")
        click.echo(f"Status: {status}")
        click.echo(f"Agents: {total} total ({alive} alive, {degraded} degraded, {down} down)")


@gateway.command("agents")
@click.option(
    "--gateway", "gateway_url", default="http://localhost:8420",
    help="Gateway URL to query.",
)
@click.option("--json", "json_out", is_flag=True, help="Output as JSON.")
def agents_cmd(gateway_url: str, json_out: bool) -> None:
    """List registered agents on the gateway."""
    httpx = _import_httpx()

    try:
        response = httpx.get(f"{gateway_url}/agents", timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception:
        click.echo(f"Error: Cannot connect to gateway at {gateway_url}", err=True)
        sys.exit(1)

    agents = data.get("agents", [])

    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    if not agents:
        click.echo("No agents registered.")
        return

    for agent in agents:
        name = agent.get("name", "?")
        status = agent.get("health", agent.get("status", "unknown"))
        caps = ", ".join(agent.get("capabilities", []))
        priority = agent.get("priority", 0)
        latency = agent.get("last_latency_ms")
        latency_str = f"{latency}ms" if latency is not None else "n/a"
        click.echo(f"  {name} [{status}]")
        click.echo(f"    capabilities: {caps or 'none'}")
        click.echo(f"    priority: {priority}  latency: {latency_str}")
