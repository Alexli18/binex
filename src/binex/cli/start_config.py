"""Provider/config wizard steps for the start wizard."""

from __future__ import annotations

import sys

import click

from binex.cli.providers import PROVIDERS, ProviderConfig
from binex.cli.start_templates import _select_prompt
from binex.cli.start_ui import _print_step


def has_rich() -> bool:
    """Proxy to binex.cli.start.has_rich for test-patchability."""
    return sys.modules["binex.cli.start"].has_rich()


def _render_provider_list(provider_names: list[str]) -> None:
    """Render provider list (Rich or plain)."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print("  Provider:")
        for i, name in enumerate(provider_names, 1):
            p = PROVIDERS[name]
            suffix = "free, local" if p.env_var is None else "API key required"
            line = Text()
            line.append(f"    {i}) ", style="dim")
            line.append(f"{name:12s}", style="bold")
            line.append(f" \u2014 {suffix}", style="dim")
            console.print(line)
    else:
        click.echo("  Provider:")
        for i, name in enumerate(provider_names, 1):
            p = PROVIDERS[name]
            suffix = "free, local" if p.env_var is None else "API key required"
            click.echo(f"    {i}) {name} \u2014 {suffix}")


def _select_provider(*, input_fn=None) -> tuple:
    """Select provider and model. Returns (ProviderConfig, model_string)."""
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    provider_names = list(PROVIDERS.keys())
    _render_provider_list(provider_names)

    choice = int(_prompt("Choose provider"))
    provider = PROVIDERS[provider_names[choice - 1]]

    model_input = _prompt(f"Model [{provider.default_model}]")
    model = model_input if model_input else provider.default_model

    # Deduplicate provider prefix
    prefix_provider = provider.agent_prefix.split("://")[-1].rstrip("/")
    if prefix_provider and model.startswith(f"{prefix_provider}/"):
        model = model[len(prefix_provider) + 1:]

    return provider, model


_BACK = object()  # sentinel for "go back to previous node"


def _print_node_header(i: int, total: int, node_id: str) -> None:
    """Print the header for a node configuration step."""
    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(
            f"\n[bold cyan]\u2500\u2500 Node {i + 1}/{total}: "
            f"{node_id} \u2500\u2500[/bold cyan]"
        )
    else:
        click.echo(f"\n\u2500\u2500 Node {i + 1}/{total}: {node_id} \u2500\u2500")


def _print_back_message(i: int, node_list: list[str]) -> int:
    """Handle back navigation and print appropriate message. Returns new index."""
    if i > 0:
        i -= 1
        if has_rich():
            from binex.cli.ui import get_console

            get_console(stderr=True).print(
                f"  [yellow]\u21a9[/yellow] Returning to "
                f"'[bold]{node_list[i]}[/bold]'"
            )
        else:
            click.echo(f"  \u21a9 Returning to '{node_list[i]}'")
    else:
        if has_rich():
            from binex.cli.ui import get_console

            get_console(stderr=True).print("  [dim]Already at the first node.[/dim]")
        else:
            click.echo("  Already at the first node.")
    return i


def _configure_all_nodes(
    node_list: list[str],
    depends_on: dict[str, list[str]],
) -> dict[str, dict]:
    """Configure all nodes with support for 'back' to return to previous node."""
    nodes_config: dict[str, dict] = {}
    i = 0
    while i < len(node_list):
        node_id = node_list[i]
        deps = depends_on.get(node_id, [])
        _print_node_header(i, len(node_list), node_id)
        cfg = _configure_node(node_id=node_id, dependencies=deps)
        if cfg is _BACK:
            i = _print_back_message(i, node_list)
            continue
        nodes_config[node_id] = cfg
        i += 1
    return nodes_config


def _handle_llm(config: dict, node_id: str, _prompt) -> None:
    """Handle LLM agent type selection."""
    provider, model = _select_provider(input_fn=_prompt)
    config["agent"] = f"{provider.agent_prefix}{model}"
    config["system_prompt"] = _select_prompt(node_id=node_id, input_fn=_prompt)


def _handle_human_review(config: dict, node_id: str, _prompt) -> None:
    """Handle human review agent type."""
    config["agent"] = "human://review"


def _handle_human_input(config: dict, node_id: str, _prompt) -> None:
    """Handle human input agent type."""
    config["agent"] = "human://input"
    config["system_prompt"] = _prompt("Prompt text for user")


def _handle_a2a(config: dict, node_id: str, _prompt) -> None:
    """Handle A2A agent type."""
    endpoint = _prompt("Endpoint URL")
    config["agent"] = f"a2a://{endpoint}"


_AGENT_TYPE_HANDLERS = {
    "1": _handle_llm,
    "2": _handle_human_review,
    "3": _handle_human_input,
    "4": _handle_a2a,
}


def _configure_node(*, node_id: str, dependencies: list[str], input_fn=None) -> dict | object:
    """Interactively configure a single node.

    Returns dict for YAML generation, or _BACK sentinel.
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(f"  Agent type for '[bold]{node_id}[/bold]':")
        for num, label in [
            ("1", "LLM (language model)"),
            ("2", "Human review (approve/reject)"),
            ("3", "Human input (free text)"),
            ("4", "A2A (external agent)"),
        ]:
            line = Text()
            line.append(f"    {num}) ", style="dim")
            line.append(label, style="bold")
            console.print(line)
        console.print("    [dim]Type 'back' to return to previous node[/dim]")
    else:
        click.echo(f"  Agent type for '{node_id}':")
        click.echo("    1) LLM (language model)")
        click.echo("    2) Human review (approve/reject)")
        click.echo("    3) Human input (free text)")
        click.echo("    4) A2A (external agent)")
        click.echo("    Type 'back' to return to previous node")
    agent_type = _prompt("Choose")

    if agent_type.lower() == "back":
        return _BACK

    config: dict = {"outputs": ["result"]}
    if dependencies:
        config["depends_on"] = dependencies

    handler = _AGENT_TYPE_HANDLERS.get(agent_type)
    if handler:
        handler(config, node_id, _prompt)

    # Back-edge

    add_back_edge = _prompt("Add review loop (back-edge)? (y/n)")
    if add_back_edge.lower() == "y":
        config["back_edge"] = _configure_back_edge(
            node_id=node_id, upstream_nodes=dependencies, input_fn=_prompt,
        )

    # Advanced params
    add_advanced = _prompt("Configure advanced parameters? (y/n)")
    if add_advanced.lower() == "y":
        advanced = _configure_advanced_params()
        config.update(advanced)

    return config


def _configure_back_edge(*, node_id: str, upstream_nodes: list[str], input_fn=None) -> dict:
    """Configure a back-edge for review loops. Returns back_edge dict."""
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print("  Return to which node on reject?")
        for i, name in enumerate(upstream_nodes, 1):
            line = Text()
            line.append(f"    {i}) ", style="dim")
            line.append(name, style="bold cyan")
            console.print(line)
    else:
        click.echo("  Return to which node on reject?")
        for i, name in enumerate(upstream_nodes, 1):
            click.echo(f"    {i}) {name}")

    choice = int(_prompt("Choose target"))
    target = upstream_nodes[choice - 1]

    max_iter_str = _prompt("Max iterations [3]") or "3"
    max_iterations = int(max_iter_str)

    return {
        "target": target,
        "when": f"${{{node_id}.decision}} == rejected",
        "max_iterations": max_iterations,
    }


class _ParamSpec:
    """Specification for a single advanced parameter collection step."""

    __slots__ = ("label", "prompt_text", "validator", "extractor")

    def __init__(self, label: str, prompt_text: str, validator, extractor):
        self.label = label
        self.prompt_text = prompt_text
        self.validator = validator
        self.extractor = extractor


def _collect_retry(value: str, _prompt) -> dict:
    """Collect retry policy fields from user input."""
    backoff = _prompt("Backoff strategy [fixed/exponential]") or "exponential"
    return {"retry_policy": {"max_retries": int(value), "backoff": backoff}}


def _configure_advanced_params(*, input_fn=None) -> dict:
    """Collect optional advanced parameters. Returns dict of extra YAML keys.

    Empty input or non-numeric input skips each parameter.
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt, default=""))
    result: dict = {}

    param_specs = [
        _ParamSpec("Budget", "Budget max_cost in $ (Enter to skip)", _is_number,
                   lambda v, _p: {"budget": {"max_cost": float(v)}}),
        _ParamSpec("Retry policy", "Max retries (Enter to skip)", _is_int,
                   _collect_retry),
        _ParamSpec("Deadline", "Deadline in seconds (Enter to skip)", _is_number,
                   lambda v, _p: {"deadline_ms": int(float(v) * 1000)}),
    ]

    use_rich = has_rich()
    console = None
    if use_rich:
        from binex.cli.ui import get_console
        console = get_console(stderr=True)

    for spec in param_specs:
        if use_rich and console:
            console.print(f"  [bold]{spec.label}[/bold] [dim](Enter to skip)[/dim]")
        value = _prompt(spec.prompt_text)
        if spec.validator(value):
            result.update(spec.extractor(value, _prompt))

    # LLM config sub-group (temperature + max_tokens)
    if use_rich and console:
        console.print("  [bold]LLM config[/bold] [dim](Enter to skip)[/dim]")
    config: dict = {}
    temp_str = _prompt("Temperature (Enter to skip)")
    if _is_number(temp_str):
        config["temperature"] = float(temp_str)
    tokens_str = _prompt("Max tokens (Enter to skip)")
    if _is_int(tokens_str):
        config["max_tokens"] = int(tokens_str)
    if config:
        result["config"] = config

    return result


def _is_number(s: str) -> bool:
    """Check if string is a valid number (int or float)."""
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def _is_int(s: str) -> bool:
    """Check if string is a valid integer."""
    if not s:
        return False
    try:
        int(s)
        return True
    except ValueError:
        return False


def _show_other_providers_submenu() -> ProviderConfig:
    """Display submenu with all providers and return the selected one."""
    all_names = list(PROVIDERS.keys())
    click.echo("\nAll providers:")
    for i, pname in enumerate(all_names, 1):
        click.echo(f"  {i}) {pname}")
    click.echo()
    sub_choice = click.prompt("Choose", type=int)
    if sub_choice < 1 or sub_choice > len(all_names):
        click.echo(f"Error: invalid choice {sub_choice}.", err=True)
        sys.exit(1)
    return PROVIDERS[all_names[sub_choice - 1]]


def _render_top_providers(top_providers: list[str]) -> None:
    """Render the top provider menu (Rich or plain)."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        for i, pname in enumerate(top_providers, 1):
            p = PROVIDERS[pname]
            suffix = "free, runs locally" if p.env_var is None else "requires API key"
            line = Text()
            line.append(f"  {i}) ", style="dim")
            line.append(f"{pname:12s}", style="bold")
            line.append(f" \u2014 {suffix}", style="dim")
            if p.env_var is None:
                line.append(" \u2b50", style="yellow")
            console.print(line)
        line = Text()
        line.append(f"  {len(top_providers) + 1}) ", style="dim")
        line.append("Other providers...", style="bold")
        console.print(line)
    else:
        for i, pname in enumerate(top_providers, 1):
            p = PROVIDERS[pname]
            suffix = "free, runs locally" if p.env_var is None else "requires API key"
            click.echo(f"  {i}) {pname:12s} \u2014 {suffix}")
        click.echo(f"  {len(top_providers) + 1}) {'Other providers...':12s}")


def _step_choose_provider() -> tuple[ProviderConfig, str, str]:
    """Step 3: Provider selection. Returns (provider, model, api_key)."""
    _print_step(3, 5, "Choose your LLM")
    click.echo()

    top_providers = ["ollama", "openai", "anthropic"]
    _render_top_providers(top_providers)
    click.echo()

    prov_choice = click.prompt("Choose", default=1, type=int)

    if prov_choice < 1 or prov_choice > len(top_providers) + 1:
        click.echo(f"Error: invalid choice {prov_choice}.", err=True)
        sys.exit(1)

    if prov_choice <= len(top_providers):
        provider: ProviderConfig = PROVIDERS[top_providers[prov_choice - 1]]
    else:
        provider = _show_other_providers_submenu()

    model = click.prompt("Model", default=provider.default_model)
    from binex.cli.start_ui import _print_confirm

    _print_confirm(f"{provider.name} / {model}")

    api_key = ""
    if provider.env_var:
        api_key = click.prompt(provider.env_var)

    return provider, model, api_key
