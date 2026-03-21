"""CLI `binex scaffold` command — generate template projects."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml  # type: ignore[import-untyped]

from typing import Any

from binex.cli.dsl_parser import PATTERNS, ParsedDSL, parse_dsl
from binex.cli.providers import PROVIDERS, ProviderConfig


@click.group("scaffold")
def scaffold_group() -> None:
    """Generate template projects for Binex agents and workflows."""


@scaffold_group.command("agent")
@click.option("--name", default="my-agent", help="Agent name")
@click.option("--dir", "directory", default=None, type=click.Path(), help="Target directory")
def scaffold_agent(name: str, directory: str | None) -> None:
    """Scaffold a new A2A agent project."""
    target = Path(directory) if directory else Path.cwd() / name

    # Fail if directory exists and is not empty
    if target.exists() and any(target.iterdir()):
        click.echo(f"Error: directory '{target}' already exists and is not empty.")
        sys.exit(1)

    try:
        target.mkdir(parents=True, exist_ok=True)

        # 1. __init__.py — empty
        (target / "__init__.py").write_text("")

        # 2. agent.py — basic handler
        (target / "agent.py").write_text(_agent_py(name))

        # 3. agent_card.json — A2A agent card
        (target / "agent_card.json").write_text(_agent_card_json(name))

        # 4. server.py — FastAPI server
        (target / "server.py").write_text(_server_py(name))

        # 5. requirements.txt
        (target / "requirements.txt").write_text(_requirements_txt())

        click.echo(f"Agent '{name}' scaffolded at {target}")

    except OSError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------

def _agent_py(name: str) -> str:
    return f'''"""Agent handler for {name}."""

from __future__ import annotations

from typing import Any


class {_class_name(name)}:
    """A simple echo agent that returns whatever it receives."""

    name = "{name}"

    async def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming message and return a response."""
        return {{
            "agent": self.name,
            "echo": message,
        }}
'''


def _agent_card_json(name: str) -> str:
    card = {
        "name": name,
        "description": f"A2A agent: {name}",
        "url": "http://localhost:8000",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "echo",
                "name": "Echo",
                "description": "Echoes back the received message.",
            }
        ],
    }
    return json.dumps(card, indent=2) + "\n"


def _server_py(name: str) -> str:
    return f'''"""Server entry point for {name}."""

from __future__ import annotations

import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from agent import {_class_name(name)}

app = FastAPI(title="{name}")
agent = {_class_name(name)}()

# Serve agent card at /.well-known/agent.json
_card_path = Path(__file__).parent / "agent_card.json"
_agent_card = json.loads(_card_path.read_text())


@app.get("/.well-known/agent.json")
async def agent_card():
    """Return the A2A agent card."""
    return _agent_card


@app.post("/execute")
async def execute(request: dict):
    """Handle a Binex A2A execution request.

    Expected: {{"task_id": str, "skill": str, "trace_id": str, "artifacts": list}}
    Returns:  {{"artifacts": list, "cost": float | null}}
    """
    result = await agent.handle(request)
    return {{"artifacts": [result], "cost": None}}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {{"status": "ok", "agent": agent.name}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''


def _requirements_txt() -> str:
    return "a2a-sdk\nfastapi\nuvicorn\n"


def _class_name(name: str) -> str:
    """Convert a kebab-case name to PascalCase class name."""
    return "".join(part.capitalize() for part in name.replace("_", "-").split("-")) + "Agent"


# ---------------------------------------------------------------------------
# scaffold workflow (T022-T024)
# ---------------------------------------------------------------------------

def _list_patterns() -> None:
    """Show available DSL patterns and exit."""
    from binex.cli import has_rich

    if has_rich():
        from binex.cli.ui import get_console, make_table

        table = make_table(
            ("Pattern", {"style": "bold", "min_width": 24}),
            ("DSL", {}),
        )
        for pname, pdsl in PATTERNS.items():
            table.add_row(pname, pdsl)
        get_console().print(table)
    else:
        click.echo(f"{'Pattern':<28} DSL")
        click.echo("-" * 60)
        for pname, pdsl in PATTERNS.items():
            click.echo(f"{pname:<28} {pdsl}")


def _resolve_dsl_source(
    pattern_name: str | None, dsl: tuple[str, ...]
) -> list[str]:
    """Return DSL strings from --pattern or positional args, or exit on error."""
    if pattern_name:
        if pattern_name not in PATTERNS:
            click.echo(
                f"Error: unknown pattern '{pattern_name}'. "
                "Use --list-patterns to see available patterns."
            )
            sys.exit(1)
        return [PATTERNS[pattern_name]]
    if dsl:
        return list(dsl)
    click.echo("Error: provide a DSL string or --pattern.")
    sys.exit(1)


@scaffold_group.command("workflow", epilog="""\b
Examples:
  binex scaffold workflow "A -> B -> C"          Linear pipeline
  binex scaffold workflow "A -> B, C -> D"       Fan-out / fan-in
  binex scaffold workflow --pattern diamond       Use predefined pattern
  binex scaffold workflow --list-patterns         Show all patterns
  binex scaffold workflow "A -> B" --no-interactive  Non-interactive stubs
""")
@click.argument("dsl", nargs=-1, metavar="DSL")
@click.option("--name", default="pipeline.yaml", help="Output filename")
@click.option("--pattern", "pattern_name", default=None, help="Use a predefined pattern")
@click.option("--list-patterns", is_flag=True, help="Show available patterns")
@click.option("--no-interactive", is_flag=True, help="Use local://echo stubs")
@click.option("--env", "gen_env", is_flag=True, help="Generate .env.example")
def scaffold_workflow(
    dsl: tuple[str, ...],
    name: str,
    pattern_name: str | None,
    list_patterns: bool,
    no_interactive: bool,
    gen_env: bool,
) -> None:
    """Scaffold a workflow YAML from a DSL topology string.

    DSL is a positional topology expression using arrows: "A -> B, C -> D".
    Nodes separated by commas run in parallel. Use --pattern for predefined
    topologies or --list-patterns to see all available patterns.
    """

    # --list-patterns: show table and exit
    if list_patterns:
        _list_patterns()
        return

    # Resolve DSL source
    dsl_strings = _resolve_dsl_source(pattern_name, dsl)

    # Parse
    try:
        parsed = parse_dsl(dsl_strings)
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)

    # Build node configs (interactive or stub)
    node_configs: dict[str, dict[str, Any]] = {}
    if no_interactive:
        for node_name in parsed.nodes:
            if _is_cao_node(node_name):
                profile = _detect_cao_profile(node_name)
                node_configs[node_name] = {
                    "agent": f"cao://{profile}",
                    "system_prompt": _CAO_PROMPTS.get(
                        node_name, "Execute this task in the terminal",
                    ),
                    "cao": {"provider": "claude_code", "output_format": "text"},
                }
            elif _is_human_node(node_name):
                htype = _detect_human_type(node_name)
                node_configs[node_name] = {
                    "agent": f"human://{htype}",
                    "system_prompt": "Provide your input"
                    if htype == "input"
                    else "Review and approve",
                }
            elif node_name in AGENTIC_PROMPTS:
                node_configs[node_name] = {
                    "agent": "local://echo",
                    "system_prompt": AGENTIC_PROMPTS[node_name],
                }
            else:
                node_configs[node_name] = {
                    "agent": "local://echo",
                    "system_prompt": "Process input",
                }
    else:
        node_configs = _interactive_node_config(parsed)

    # Generate YAML
    workflow = _build_workflow_yaml(parsed, node_configs, name)
    out_path = Path(name)
    out_path.write_text(yaml.dump(workflow, default_flow_style=False, sort_keys=False))
    click.echo(f"Workflow written to {out_path}")

    # --env: generate .env.example
    if gen_env:
        _generate_env_example(out_path.parent)


# Agentic node → prompt file mapping (used in --no-interactive mode).
AGENTIC_PROMPTS: dict[str, str] = {
    "generator": "file://prompts/wf-generator.md",
    "critic": "file://prompts/wf-critic.md",
    "refiner": "file://prompts/wf-refiner.md",
    "planner": "file://prompts/wf-task-decomposer.md",
    "executor": "file://prompts/wf-executor.md",
    "verifier": "file://prompts/wf-verifier.md",
    "agent": "file://prompts/wf-agent.md",
    "simulator": "file://prompts/wf-simulator.md",
}

_CAO_KEYWORDS = {"cao", "cli_agent", "terminal"}
_CAO_PROFILE_MAP: dict[str, str] = {
    "writer": "developer",
    "impl": "developer",
    "coder": "developer",
    "fixer": "developer",
    "tester": "developer",
    "tests": "developer",
    "docs": "developer",
    "deps": "developer",
    "lint": "developer",
    "reviewer": "reviewer",
    "security": "reviewer",
    "supervisor": "code_supervisor",
    "agent": "developer",
}

_CAO_PROMPTS: dict[str, str] = {
    "cao_agent": "Analyze the project and report your findings.",
    "cao_writer": "Write the code and save it to a file.",
    "cao_tester": "Run the tests and report pass/fail results.",
    "cao_reviewer": "Review the code for quality and correctness.",
    "cao_supervisor": "Break the task into subtasks and assign them.",
    "cao_fixer": "Apply the reviewer's feedback and fix all issues.",
    "cao_impl": "Implement the core code based on the plan.",
    "cao_tests": "Write and run a comprehensive test suite.",
    "cao_docs": "Write documentation: README and API reference.",
    "cao_deps": "Check dependencies for outdated or unused packages.",
    "cao_security": "Run a security audit on the project.",
    "cao_lint": "Run linters and report code quality issues.",
}


def _is_cao_node(node_name: str) -> bool:
    """Check if node name suggests a CAO CLI agent step."""
    lower = node_name.lower().replace("-", "_")
    return lower.startswith("cao_") or any(kw in lower for kw in _CAO_KEYWORDS)


def _detect_cao_profile(node_name: str) -> str:
    """Map CAO node name to a profile name."""
    lower = node_name.lower().replace("-", "_")
    suffix = lower.removeprefix("cao_")
    return _CAO_PROFILE_MAP.get(suffix, "developer")


_HUMAN_APPROVE_KEYWORDS = {"approve", "confirm", "gate"}
_HUMAN_INPUT_KEYWORDS = {"input", "feedback", "edit", "ask"}
_HUMAN_ALL_KEYWORDS = _HUMAN_APPROVE_KEYWORDS | _HUMAN_INPUT_KEYWORDS | {"human", "review"}


def _is_human_node(node_name: str) -> bool:
    """Check if node name suggests a human-in-the-loop step."""
    lower = node_name.lower().replace("-", "_")
    return any(kw in lower for kw in _HUMAN_ALL_KEYWORDS)


def _detect_human_type(node_name: str) -> str:
    """Detect whether a human node is approve or input type."""
    lower = node_name.lower().replace("-", "_")
    if any(kw in lower for kw in _HUMAN_INPUT_KEYWORDS):
        return "input"
    return "approve"


def _configure_human_node(node_name: str) -> dict[str, Any] | None:
    """Try to configure a human node interactively. Return config or None."""
    if not _is_human_node(node_name):
        return None

    htype = _detect_human_type(node_name)
    default_system_prompt = (
        "Provide your input" if htype == "input"
        else "Review and approve"
    )
    use_human = click.prompt(
        f"Detected human node. Use human://{htype}?",
        type=click.Choice(["y", "n"]),
        default="y",
    )
    if use_human != "y":
        return None

    system_prompt = click.prompt(
        "System prompt",
        default=default_system_prompt,
    )
    return {
        "agent": f"human://{htype}",
        "system_prompt": system_prompt,
    }


def _configure_llm_node(
    provider_list: list[ProviderConfig],
    prev_provider: ProviderConfig | None,
    prev_model: str | None,
) -> dict[str, Any]:
    """Prompt user for provider/model/system_prompt for an LLM node.

    Returns dict with keys: config, provider, model.
    """
    click.echo("Providers:")
    for i, p in enumerate(provider_list, 1):
        click.echo(f"  {i}. {p.name} ({p.default_model})")

    hint = ""
    if prev_provider is not None:
        hint = f" [Enter = same as previous: {prev_provider.name}]"

    raw = click.prompt(
        f"Choose provider (1-{len(provider_list)}){hint}",
        default="",
        show_default=False,
    )
    if raw == "" and prev_provider is not None:
        prov = prev_provider
    else:
        try:
            idx = int(raw) - 1
            prov = provider_list[idx]
        except (ValueError, IndexError):
            click.echo("Invalid choice, using first provider.")
            prov = provider_list[0]

    # Reset model default when provider changes
    if prev_provider is not None and prov.name == prev_provider.name:
        default_model = prev_model or prov.default_model
    else:
        default_model = prov.default_model

    model = click.prompt("Model", default=default_model)
    system_prompt = click.prompt("System prompt", default="Process input")

    # Strip litellm provider prefix from model if agent_prefix
    # already contains it (avoid llm://gemini/gemini/model)
    prefix_provider = prov.agent_prefix.replace("llm://", "").rstrip("/")
    if prefix_provider and model.startswith(f"{prefix_provider}/"):
        model_stripped = model[len(prefix_provider) + 1:]
        agent_uri = f"{prov.agent_prefix}{model_stripped}"
    else:
        agent_uri = f"{prov.agent_prefix}{model}"

    return {
        "config": {"agent": agent_uri, "system_prompt": system_prompt},
        "provider": prov,
        "model": model,
    }


def _interactive_node_config(parsed: ParsedDSL) -> dict[str, dict[str, Any]]:
    """Prompt user for provider/model/system_prompt per node."""
    provider_list = list(PROVIDERS.values())
    configs: dict[str, dict[str, Any]] = {}
    prev_provider = None
    prev_model = None

    for node_name in parsed.nodes:
        click.echo(f"\n--- Node: {node_name} ---")

        # Auto-detect human nodes
        human_cfg = _configure_human_node(node_name)
        if human_cfg is not None:
            configs[node_name] = human_cfg
            continue

        result = _configure_llm_node(provider_list, prev_provider, prev_model)
        configs[node_name] = result["config"]
        prev_provider = result["provider"]
        prev_model = result["model"]

    return configs


def _build_workflow_yaml(
    parsed: ParsedDSL,
    node_configs: dict[str, dict[str, Any]],
    filename: str,
) -> dict[str, Any]:
    """Build workflow dict suitable for YAML serialization."""
    stem = Path(filename).stem
    nodes: dict[str, dict[str, Any]] = {}

    for node_name in parsed.nodes:
        cfg = node_configs[node_name]
        deps = parsed.depends_on.get(node_name, [])

        # Build inputs: reference upstream outputs
        inputs: dict[str, str] = {}
        if deps:
            for dep in deps:
                inputs[dep] = f"${{{dep}.output}}"
        else:
            inputs["query"] = "${user.query}"

        node_spec: dict[str, Any] = {
            "agent": cfg["agent"],
            "system_prompt": cfg["system_prompt"],
            "inputs": inputs,
            "outputs": ["output"],
        }
        if deps:
            node_spec["depends_on"] = deps

        nodes[node_name] = node_spec

    return {
        "name": stem,
        "description": f"Auto-generated workflow: {stem}",
        "nodes": nodes,
    }


def _generate_env_example(directory: Path) -> None:
    """Write a .env.example with common API key placeholders."""
    lines = [
        "# API keys for LLM providers",
        "# Uncomment and fill in the ones you need",
        "",
    ]
    for prov in PROVIDERS.values():
        if prov.env_var:
            lines.append(f"# {prov.env_var}=your-key-here")
    env_path = directory / ".env.example"
    env_path.write_text("\n".join(lines) + "\n")
    click.echo(f"Environment template written to {env_path}")
