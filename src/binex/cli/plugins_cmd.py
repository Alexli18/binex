"""CLI `binex plugins` command group — list and check plugins."""

from __future__ import annotations

import json
import sys

import click
import yaml

from binex.plugins import PluginRegistry

_BUILTINS = [
    {"prefix": "local", "adapter": "LocalPythonAdapter"},
    {"prefix": "llm", "adapter": "LLMAdapter"},
    {"prefix": "human", "adapter": "HumanApprovalAdapter / HumanInputAdapter"},
    {"prefix": "a2a", "adapter": "A2AAgentAdapter"},
]

_BUILTIN_PREFIXES = frozenset(b["prefix"] for b in _BUILTINS)


@click.group("plugins")
def plugins_group() -> None:
    """Manage adapter plugins."""


@plugins_group.command("list")
@click.option("--json-output", "--json", "json_out", is_flag=True, help="Output as JSON")
def list_plugins(json_out: bool) -> None:
    """Show built-in adapters and installed plugins."""
    registry = PluginRegistry()
    registry.discover()
    plugins = registry.all_plugins()

    if json_out:
        data = {
            "builtins": _BUILTINS,
            "plugins": [
                {"prefix": p["prefix"], "package": p["package_name"], "version": p["version"]}
                for p in plugins
            ],
        }
        click.echo(json.dumps(data, indent=2))
        return

    click.echo("Built-in adapters:")
    for b in _BUILTINS:
        click.echo(f"  {b['prefix']}://     {b['adapter']}")

    click.echo()
    if plugins:
        click.echo("Installed plugins:")
        for p in plugins:
            ver = f" ({p['version']})" if p["version"] else ""
            click.echo(f"  {p['prefix']}://  {p['package_name'] or p['name']}{ver}")
    else:
        click.echo("No plugins installed.")


@plugins_group.command("check")
@click.argument("workflow_file", type=click.Path(exists=True))
def check_plugins(workflow_file: str) -> None:
    """Validate that all agent URIs in a workflow are resolvable."""
    with open(workflow_file) as f:
        data = yaml.safe_load(f)

    nodes = data.get("nodes", {})
    if not nodes:
        click.echo("No nodes found in workflow.")
        return

    registry = PluginRegistry()
    registry.discover()
    plugin_map = {p["prefix"]: p for p in registry.all_plugins()}

    missing_count = 0

    for node_id, node_data in nodes.items():
        agent = node_data.get("agent", "")
        prefix = agent.split("://")[0] if "://" in agent else agent

        if prefix in _BUILTIN_PREFIXES:
            click.echo(f"\u2713 {agent}    built-in")
        elif prefix in plugin_map:
            p = plugin_map[prefix]
            ver = f" {p['version']}" if p["version"] else ""
            click.echo(f"\u2713 {agent}    plugin ({p['package_name'] or p['name']}{ver})")
        else:
            click.echo(f"\u2717 {agent}    not found \u2014 pip install binex-{prefix}")
            missing_count += 1

    if missing_count:
        click.echo(f"\n{missing_count} missing adapter(s). Workflow cannot run.")
        sys.exit(1)
