"""Constructor (node editor) for the start wizard."""

from __future__ import annotations

import sys

import click

from binex.cli.start_config import _configure_advanced_params, _select_provider
from binex.cli.start_templates import _select_prompt_variant
from binex.cli.start_ui import _preview_yaml


def _parse_comma_list(input_str: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped, non-empty items."""
    if not input_str:
        return []
    return [item.strip() for item in input_str.split(",") if item.strip()]


def _select_node_by_number(
    node_list: list[str],
    prompt_fn,
    prompt_text: str = "Choose which node?",
) -> str | None:
    """Display numbered node list and prompt user to select one by number.

    Returns the selected node name, or None if the choice is invalid.
    """
    for i, name in enumerate(node_list, 1):
        click.echo(f"    {i}) {name}")

    try:
        choice = int(prompt_fn(prompt_text))
    except ValueError:
        click.echo("  Invalid choice.")
        return None
    if choice < 1 or choice > len(node_list):
        click.echo("  Invalid choice.")
        return None

    return node_list[choice - 1]


def has_rich() -> bool:
    """Proxy to binex.cli.start.has_rich for test-patchability."""
    return sys.modules["binex.cli.start"].has_rich()


def _constructor_loop(
    nodes_config: dict[str, dict],
    edges: list[tuple[str, str]],
    *,
    input_fn=None,
    node_roles: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Main constructor loop: display DAG, menu for add/delete/edit/move/preview/done."""
    _prompt = input_fn or (lambda p: click.prompt(p))

    from binex.cli.ui import render_dag_ascii

    while True:
        # Display current graph
        node_names = list(nodes_config.keys())
        dag_str = render_dag_ascii(node_names, edges)

        if has_rich():
            from binex.cli.ui import get_console

            console = get_console(stderr=True)
            console.print("\n[bold cyan]\u2500\u2500 Constructor "
                          "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                          "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                          "\u2500\u2500\u2500\u2500[/bold cyan]")
            console.print(f"Current graph: [bold]{dag_str}[/bold]")
            console.print(
                f"Nodes: {len(nodes_config)} | Edges: {len(edges)}"
            )
            console.print()
            console.print("  [bold][a][/bold] Add node")
            console.print("  [bold][d][/bold] Delete node")
            console.print("  [bold][e][/bold] Edit node")
            console.print("  [bold][m][/bold] Move node")
            console.print("  [bold][p][/bold] Preview YAML")
            console.print("  [bold][done][/bold] Finish")
        else:
            click.echo("\n\u2500\u2500 Constructor "
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
                        "\u2500\u2500\u2500\u2500")
            click.echo(f"Current graph: {dag_str}")
            click.echo(f"Nodes: {len(nodes_config)} | Edges: {len(edges)}")
            click.echo()
            click.echo("  [a] Add node")
            click.echo("  [d] Delete node")
            click.echo("  [e] Edit node")
            click.echo("  [m] Move node")
            click.echo("  [p] Preview YAML")
            click.echo("  [done] Finish")

        action = _prompt("Action").strip().lower()

        if action == "done":
            return nodes_config
        elif action == "a":
            nodes_config, edges = _constructor_add_node(
                nodes_config, edges, input_fn=_prompt,
            )
        elif action == "d":
            nodes_config, edges = _constructor_delete_node(
                nodes_config, edges, input_fn=_prompt,
            )
        elif action == "e":
            nodes_config = _constructor_edit_node(
                nodes_config, edges, input_fn=_prompt,
                node_roles=node_roles,
            )
        elif action == "m":
            nodes_config, edges = _constructor_move_node(
                nodes_config, edges, input_fn=_prompt,
            )
        elif action == "p":
            from binex.cli.start import build_custom_workflow

            yaml_content, _ = build_custom_workflow(
                name="constructor-preview", nodes_config=nodes_config,
            )
            _preview_yaml(yaml_content)


def _constructor_add_node(
    nodes_config: dict[str, dict],
    edges: list[tuple[str, str]],
    *,
    input_fn=None,
) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Add a new node to the graph."""
    _prompt = input_fn or (lambda p: click.prompt(p))

    name = _prompt("Node name")
    if name in nodes_config:
        click.echo(f"  Node '{name}' already exists.")
        return nodes_config, edges

    # Select prompt
    prompt_str = _select_prompt_variant(
        role_name=name, input_fn=_prompt,
    )

    # Select agent
    provider, model = _select_provider(input_fn=_prompt)
    agent_uri = f"{provider.agent_prefix}{model}"

    # Dependencies
    dep_str = _prompt("Depends on (comma-separated, or empty)")
    deps = [d.strip() for d in dep_str.split(",") if d.strip()] \
        if dep_str else []

    cfg: dict = {
        "agent": agent_uri,
        "system_prompt": prompt_str,
        "outputs": ["result"],
    }
    if deps:
        cfg["depends_on"] = deps
        for d in deps:
            if d in nodes_config:
                edges.append((d, name))

    nodes_config[name] = cfg
    click.echo(f"  Added node '{name}'")
    return nodes_config, edges


def _constructor_delete_node(
    nodes_config: dict[str, dict],
    edges: list[tuple[str, str]],
    *,
    input_fn=None,
) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Delete a node and its edges."""
    _prompt = input_fn or (lambda p: click.prompt(p))

    node_list = list(nodes_config.keys())
    for i, name in enumerate(node_list, 1):
        click.echo(f"    {i}) {name}")

    try:
        choice = int(_prompt("Delete which node?"))
    except ValueError:
        click.echo("  Invalid choice.")
        return nodes_config, edges
    if choice < 1 or choice > len(node_list):
        click.echo("  Invalid choice.")
        return nodes_config, edges

    target = node_list[choice - 1]
    del nodes_config[target]
    edges = [(s, d) for s, d in edges if s != target and d != target]

    # Remove from depends_on of other nodes
    for cfg in nodes_config.values():
        deps = cfg.get("depends_on", [])
        if target in deps:
            deps.remove(target)

    click.echo(f"  Deleted node '{target}'")
    return nodes_config, edges


def _constructor_edit_node(
    nodes_config: dict[str, dict],
    edges: list[tuple[str, str]],
    *,
    input_fn=None,
    node_roles: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Edit a node's prompt, agent, or config."""
    _prompt = input_fn or (lambda p: click.prompt(p))

    node_list = list(nodes_config.keys())
    for i, name in enumerate(node_list, 1):
        click.echo(f"    {i}) {name}")

    try:
        choice = int(_prompt("Edit which node?"))
    except ValueError:
        click.echo("  Invalid choice.")
        return nodes_config
    if choice < 1 or choice > len(node_list):
        click.echo("  Invalid choice.")
        return nodes_config

    target = node_list[choice - 1]
    cfg = nodes_config[target]

    click.echo(f"  Editing '{target}':")
    click.echo("    [p] Prompt")
    click.echo("    [a] Agent (provider/model)")
    click.echo("    [c] Config (advanced params)")
    click.echo("    [b] Back")

    sub = _prompt("Choose").strip().lower()

    if sub == "p":
        # Look up role from node_roles mapping, fallback to node name
        role_name = (node_roles or {}).get(target, target)
        cfg["system_prompt"] = _select_prompt_variant(
            role_name=role_name, input_fn=_prompt,
        )
    elif sub == "a":
        provider, model = _select_provider(input_fn=_prompt)
        cfg["agent"] = f"{provider.agent_prefix}{model}"
    elif sub == "c":
        advanced = _configure_advanced_params(input_fn=_prompt)
        cfg.update(advanced)

    nodes_config[target] = cfg
    return nodes_config


def _constructor_move_node(
    nodes_config: dict[str, dict],
    edges: list[tuple[str, str]],
    *,
    input_fn=None,
) -> tuple[dict[str, dict], list[tuple[str, str]]]:
    """Move a node by changing its edges."""
    _prompt = input_fn or (lambda p: click.prompt(p))

    node_list = list(nodes_config.keys())
    target = _select_node_by_number(node_list, _prompt, "Move which node?")
    if target is None:
        return nodes_config, edges

    # Remove old edges for this node
    edges = [(s, d) for s, d in edges if s != target and d != target]

    # New parents
    parent_str = _prompt(f"New parents for '{target}' (comma-separated, or empty)")
    parents = _parse_comma_list(parent_str)

    # New children
    child_str = _prompt(f"New children of '{target}' (comma-separated, or empty)")
    children = _parse_comma_list(child_str)

    for p in parents:
        if p in nodes_config:
            edges.append((p, target))
    for c in children:
        if c in nodes_config:
            edges.append((target, c))

    # Update depends_on
    nodes_config[target]["depends_on"] = parents if parents else []

    click.echo(f"  Moved node '{target}'")
    return nodes_config, edges
