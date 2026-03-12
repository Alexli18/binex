"""CLI `binex start` — interactive wizard for creating agent workflows."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import yaml

from binex.cli import has_rich
from binex.cli.dsl_parser import PATTERNS, parse_dsl
from binex.cli.prompt_roles import (
    CATEGORY_ICONS,
    CATEGORY_ORDER,
    TEMPLATE_CATEGORIES,
)
from binex.cli.providers import PROVIDERS, ProviderConfig
from binex.cli.start_config import (
    _configure_all_nodes,
    _step_choose_provider,
)
from binex.cli.start_templates import (
    _NODE_PROMPT_FILES,
    _copy_prompts_to_project,
)
from binex.cli.start_ui import (
    _preview_yaml,
    _print_banner,
    _print_confirm,
    _print_done_panel,
    _print_dsl_preview,
    _print_file_created,
    _print_step,
)

# ---------------------------------------------------------------------------
# YAML generation
# ---------------------------------------------------------------------------

def build_start_workflow(
    *,
    dsl: str,
    agent_prefix: str,
    model: str,
    user_input: bool = False,
    user_prompt: str = "Enter your input:",
) -> str:
    """Generate workflow YAML string from a DSL expression and provider info.

    Returns a valid YAML string suitable for ``binex run``.
    """
    parsed = parse_dsl([dsl])
    # Strip provider prefix from model if it duplicates agent_prefix
    # e.g. agent_prefix="llm://ollama/", model="ollama/gemma3:4b"
    # -> should produce "llm://ollama/gemma3:4b", not "llm://ollama/ollama/gemma3:4b"
    prefix_provider = agent_prefix.split("://")[-1].rstrip("/")
    if prefix_provider and model.startswith(f"{prefix_provider}/"):
        model = model[len(prefix_provider) + 1:]
    agent_uri = f"{agent_prefix}{model}"

    nodes: dict[str, dict] = {}

    # Optional user_input node prepended
    if user_input:
        first_nodes = [n for n in parsed.nodes if not parsed.depends_on.get(n)]
        nodes["user_input"] = {
            "agent": "human://input",
            "system_prompt": user_prompt,
            "outputs": ["result"],
        }
        # Make original root nodes depend on user_input
        for n in first_nodes:
            if n not in parsed.depends_on:
                parsed.depends_on[n] = []
            parsed.depends_on[n].append("user_input")

    needed_prompts: set[str] = set()
    for node_name in parsed.nodes:
        node_def: dict = {"agent": agent_uri, "outputs": ["result"]}
        # Use file:// prompt reference if a bundled prompt exists
        prompt_file = _NODE_PROMPT_FILES.get(node_name)
        if prompt_file:
            node_def["system_prompt"] = f"file://prompts/{prompt_file}"
            needed_prompts.add(prompt_file)
        deps = parsed.depends_on.get(node_name, [])
        if deps:
            node_def["depends_on"] = deps
        nodes[node_name] = node_def

    workflow = {
        "name": "start-wizard-workflow",
        "nodes": nodes,
    }
    yaml_str = yaml.dump(
        workflow, default_flow_style=False, sort_keys=False,
    )
    return yaml_str, needed_prompts


_OPTIONAL_NODE_KEYS = (
    "depends_on", "back_edge", "budget", "retry_policy", "deadline_ms", "config",
)


def _build_node_dict(cfg: dict, needed_prompts: set[str]) -> dict:
    """Build a single node dict from config, collecting needed prompts."""
    node: dict = {"agent": cfg["agent"]}

    if cfg.get("system_prompt"):
        node["system_prompt"] = cfg["system_prompt"]
        sp = cfg["system_prompt"]
        if sp.startswith("file://prompts/") and sp.endswith(".md"):
            needed_prompts.add(sp.removeprefix("file://prompts/"))

    node["outputs"] = cfg.get("outputs", ["result"])

    for key in _OPTIONAL_NODE_KEYS:
        if cfg.get(key):
            node[key] = cfg[key]

    return node


def build_custom_workflow(*, name: str, nodes_config: dict[str, dict]) -> tuple[str, set[str]]:
    """Generate workflow YAML from per-node configuration dicts.

    Returns (yaml_string, set_of_needed_prompt_files).
    """
    needed_prompts: set[str] = set()
    nodes: dict[str, dict] = {}

    for node_id, cfg in nodes_config.items():
        nodes[node_id] = _build_node_dict(cfg, needed_prompts)

    workflow = {"name": name, "nodes": nodes}
    yaml_str = yaml.dump(workflow, default_flow_style=False, sort_keys=False)
    return yaml_str, needed_prompts


# ---------------------------------------------------------------------------
# Run workflow (optional post-generation execution)
# ---------------------------------------------------------------------------

def _get_stores():
    """Create default stores. Extracted for test patching."""
    from binex.cli import get_stores
    return get_stores()


async def _execute(workflow_path: str) -> tuple:
    """Load and execute a workflow, returning (summary, errors, artifacts)."""
    from binex.cli.adapter_registry import register_workflow_adapters
    from binex.runtime.orchestrator import Orchestrator
    from binex.workflow_spec.loader import load_workflow

    spec = load_workflow(workflow_path)
    execution_store, artifact_store = _get_stores()

    orch = Orchestrator(
        artifact_store=artifact_store,
        execution_store=execution_store,
    )

    # Progress callback
    counter = [0]
    total = len(spec.nodes)
    original_execute = orch._execute_node

    async def _progress_execute(
        spec_, dag_, scheduler_, run_id_, trace_id_, node_id_, node_artifacts_,
        accumulated_cost_=0.0, node_artifacts_history_=None,
    ):
        counter[0] += 1
        if has_rich():
            from binex.cli.ui import get_console

            get_console(stderr=True).print(
                f"  [cyan][{counter[0]}/{total}][/cyan] "
                f"[bold]{node_id_}[/bold] [dim]...[/dim]"
            )
        else:
            click.echo(f"  [{counter[0]}/{total}] {node_id_} ...", err=True)
        await original_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_,
            node_id_, node_artifacts_, accumulated_cost_, node_artifacts_history_,
        )

    orch._execute_node = _progress_execute

    register_workflow_adapters(orch.dispatcher, spec)

    try:
        summary = await orch.run_workflow(spec)
        errors = []
        records = await execution_store.list_records(summary.run_id)
        for rec in records:
            if rec.error:
                errors.append((rec.task_id, rec.error))
        all_artifacts = await artifact_store.list_by_run(summary.run_id)
        return spec, summary, errors, all_artifacts
    finally:
        await execution_store.close()


def _run_workflow(workflow_path: str) -> None:
    """Run a workflow and display results."""
    spec, summary, errors, artifacts = asyncio.run(_execute(workflow_path))

    for node_id, err in errors:
        click.echo(f"  [{node_id}] Error: {err}", err=True)

    click.echo(f"Run ID: {summary.run_id}")
    click.echo(f"Status: {summary.status}")
    click.echo(f"Nodes: {summary.completed_nodes}/{summary.total_nodes} completed")

    if summary.status == "completed" and artifacts:
        from binex.cli import render_terminal_artifacts

        all_deps = {dep for node in spec.nodes.values() for dep in node.depends_on}
        terminal_nodes = [nid for nid in spec.nodes if nid not in all_deps]
        render_terminal_artifacts(artifacts, terminal_nodes)


# ---------------------------------------------------------------------------
# Category navigation (Phase 3 — US1)
# ---------------------------------------------------------------------------

def _step_choose_category(*, input_fn=None) -> str | None:
    """Display 8 categories. Returns category name, 'c' for constructor, or None for quit."""
    _prompt = input_fn or (lambda p: click.prompt(p))

    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print("\n  [bold cyan]Category:[/bold cyan]")
        for i, cat in enumerate(CATEGORY_ORDER, 1):
            icon = CATEGORY_ICONS.get(cat, "\u2022")
            count = len(TEMPLATE_CATEGORIES.get(cat, []))
            label = cat.capitalize()
            line = Text()
            line.append(f"    {i}) ", style="dim")
            line.append(f"{icon} {label:16s}", style="bold")
            line.append(f" \u2014 {count} templates", style="dim")
            console.print(line)
        console.print()
        line = Text()
        line.append("    c) ", style="dim")
        line.append("\U0001f527 Empty constructor", style="bold")
        line.append(" \u2014 build your own from scratch", style="dim")
        console.print(line)
    else:
        click.echo("\n  Category:")
        for i, cat in enumerate(CATEGORY_ORDER, 1):
            icon = CATEGORY_ICONS.get(cat, "\u2022")
            count = len(TEMPLATE_CATEGORIES.get(cat, []))
            label = cat.capitalize()
            click.echo(f"    {i}) {icon} {label:16s} \u2014 {count} templates")
        click.echo()
        click.echo("    c) \U0001f527 Empty constructor \u2014 build your own from scratch")

    choice = _prompt("Choose")
    choice = choice.strip().lower()

    if choice == "c":
        return "c"
    if choice in ("b", "q"):
        return None

    try:
        idx = int(choice)
    except ValueError:
        return None
    if 1 <= idx <= len(CATEGORY_ORDER):
        return CATEGORY_ORDER[idx - 1]
    return None


def _template_dag_str(t) -> str:
    """Build an ASCII DAG string from a template's DSL."""
    from binex.cli.ui import render_dag_ascii

    parsed = parse_dsl([t.dsl])
    nodes = list(parsed.nodes)
    edges = []
    for n, deps in parsed.depends_on.items():
        for d in deps:
            edges.append((d, n))
    return render_dag_ascii(nodes, edges)


def _render_template_list_rich(label: str, templates: list) -> None:
    """Render template list in Rich format."""
    from rich.text import Text

    from binex.cli.ui import get_console

    console = get_console(stderr=True)
    console.print(f"\n  [bold cyan]{label}:[/bold cyan]")
    for i, t in enumerate(templates, 1):
        dag_str = _template_dag_str(t)
        line = Text()
        line.append(f"    {i}) ", style="dim")
        line.append(f"{t.label:20s}", style="bold")
        line.append(f" {dag_str}", style="dim")
        console.print(line)
    console.print("\n  [dim][b] Back to categories[/dim]")


def _render_template_list_plain(label: str, templates: list) -> None:
    """Render template list in plain text."""
    click.echo(f"\n  {label}:")
    for i, t in enumerate(templates, 1):
        dag_str = _template_dag_str(t)
        click.echo(f"    {i}) {t.label:20s} {dag_str}")
    click.echo("\n  [b] Back to categories")


def _step_pick_template(category: str, *, input_fn=None):
    """Display templates in a category. Returns TemplateConfig or None for back."""
    _prompt = input_fn or (lambda p: click.prompt(p))
    templates = TEMPLATE_CATEGORIES.get(category, [])

    label = category.capitalize()
    if has_rich():
        _render_template_list_rich(label, templates)
    else:
        _render_template_list_plain(label, templates)

    choice = _prompt("Choose")
    choice = choice.strip().lower()

    if choice == "b":
        return None

    try:
        idx = int(choice)
    except ValueError:
        return None
    if 1 <= idx <= len(templates):
        return templates[idx - 1]
    return None


# ---------------------------------------------------------------------------
# Wizard steps
# ---------------------------------------------------------------------------

TOTAL_STEPS = 5


def _step_choose_template() -> tuple[str, str, str]:
    """Step 1: Two-level category -> template selection.

    Returns (dsl, default_name, user_prompt_text).
    """
    _print_step(1, TOTAL_STEPS, "Choose a template")

    while True:
        cat = _step_choose_category()
        if cat is None:
            click.echo("Cancelled.")
            sys.exit(0)
        if cat == "c":
            return _step_custom_template()

        tpl = _step_pick_template(cat)
        if tpl is None:
            continue

        _print_confirm(f"{tpl.label}")
        _print_dsl_preview(tpl.dsl)
        return tpl.dsl, tpl.default_name, f"Input for {tpl.label}:"


def _collect_env_vars(nodes_config: dict[str, dict]) -> str:
    """Collect env vars from node agents and return .env content."""
    env_lines: list[str] = []
    seen_vars: set[str] = set()
    for cfg in nodes_config.values():
        agent = cfg.get("agent", "")
        for prov in PROVIDERS.values():
            if agent.startswith(prov.agent_prefix) and prov.env_var:
                if prov.env_var not in seen_vars:
                    env_lines.append(f"{prov.env_var}=\n")
                    seen_vars.add(prov.env_var)
    return "".join(env_lines)


def _resolve_project_dir(project_name: str) -> Path:
    """Resolve and validate project directory. Exits on error."""
    try:
        project_dir = Path.cwd() / project_name
    except FileNotFoundError:
        click.echo(
            "Error: current directory does not exist. "
            "Please cd to a valid directory and try again.",
            err=True,
        )
        sys.exit(1)

    if project_dir.exists() and any(project_dir.iterdir()):
        click.echo(
            f"Error: directory '{project_name}' already exists and is not empty.",
            err=True,
        )
        sys.exit(1)

    return project_dir


def _write_custom_project_files(
    project_dir: Path, yaml_content: str,
    needed_prompts: set[str], nodes_config: dict[str, dict],
) -> None:
    """Write all project files for the custom wizard."""
    project_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "workflow.yaml").write_text(yaml_content)
    _print_file_created("workflow.yaml")

    if needed_prompts:
        _copy_prompts_to_project(project_dir, needed_prompts)
        _print_file_created(f"prompts/ ({len(needed_prompts)} files)")

    (project_dir / ".env").write_text(_collect_env_vars(nodes_config))
    _print_file_created(".env")

    (project_dir / ".gitignore").write_text(".binex/\n.env\n__pycache__/\n*.pyc\n")
    _print_file_created(".gitignore")


def _custom_interactive_wizard(dsl: str) -> None:
    """Full custom wizard: configure each node, preview, save project.

    This handles everything from topology through file generation so the
    caller can ``sys.exit(0)`` afterwards, bypassing the regular
    provider/user-input/project steps in ``start_cmd``.
    """
    parsed = parse_dsl([dsl])

    # Phase 1 — per-node configuration (with 'back' support)
    node_list = list(parsed.nodes)
    nodes_config = _configure_all_nodes(node_list, parsed.depends_on)

    # Phase 2 — build YAML and preview
    yaml_content, needed_prompts = build_custom_workflow(
        name="custom-workflow", nodes_config=nodes_config,
    )
    _preview_yaml(yaml_content)

    # Phase 3 — confirm save
    save = click.prompt("Save this workflow?", default="y",
                        type=click.Choice(["y", "n"], case_sensitive=False))
    if save.lower() != "y":
        action = click.prompt(
            "1) Return to config  2) Cancel",
            default="2", type=click.Choice(["1", "2"]),
        )
        if action == "2":
            click.echo("Cancelled.")
            return
        # action == "1": re-configure
        nodes_config = _configure_all_nodes(node_list, parsed.depends_on)
        yaml_content, needed_prompts = build_custom_workflow(
            name="custom-workflow", nodes_config=nodes_config,
        )
        _preview_yaml(yaml_content)

    # Phase 4 — project name & generation
    project_name = click.prompt("Project name", default="my-project")
    project_dir = _resolve_project_dir(project_name)
    _write_custom_project_files(project_dir, yaml_content, needed_prompts, nodes_config)

    click.echo()

    run_now = click.prompt(
        "Run the workflow now?",
        default="y",
        type=click.Choice(["y", "n"], case_sensitive=False),
    )

    if run_now.lower() == "y":
        _run_workflow(str(project_dir / "workflow.yaml"))
    else:
        _print_done_panel(project_name)


def _step_custom_template() -> tuple[str, str, str]:
    """Custom template sub-step: DSL or step-by-step topology builder.

    When the full custom wizard is used (node-by-node configuration),
    this function calls ``_custom_interactive_wizard`` and exits via
    ``sys.exit(0)`` so the caller never reaches the global provider steps.
    Otherwise it falls back to the original behaviour returning
    ``(dsl, default_name, user_prompt_text)``.
    """
    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print()
        console.print(
            "  [bold]1)[/bold] [cyan]DSL[/cyan] \u2014 write topology as arrows"
            " (e.g. A -> B, C -> D)"
        )
        console.print(
            "  [bold]2)[/bold] [cyan]Step-by-step[/cyan]"
            " \u2014 build nodes one at a time"
        )
        console.print()
    else:
        click.echo()
        click.echo("  1) DSL \u2014 write topology as arrows (e.g. A -> B, C -> D)")
        click.echo("  2) Step-by-step \u2014 build nodes one at a time")
        click.echo()

    mode = click.prompt("Choose mode", type=click.Choice(["1", "2"]), default="1")

    if mode == "1":
        dsl = _step_custom_dsl_topology()
    else:
        dsl = _step_mode_topology()
        _print_confirm("Custom workflow")
        _print_dsl_preview(dsl)

    # Run the full custom interactive wizard and exit
    _custom_interactive_wizard(dsl)
    sys.exit(0)

    # Fallback (never reached, keeps type-checker happy)
    return dsl, "my-project", "Enter your input:"


def _step_custom_dsl_topology() -> str:
    """Show DSL help, get user topology via direct input. Returns DSL string."""
    if has_rich():
        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        help_text = (
            "A workflow is a chain of agents connected by [bold cyan]arrows[/bold cyan] "
            "([cyan]->[/cyan]).\n"
            "Agents on the same level (separated by [bold cyan]commas[/bold cyan]) "
            "run in parallel.\n\n"
            "[bold]Examples:[/bold]\n"
            "  [cyan]A -> B -> C[/cyan]                   "
            "[dim]\u2014 three steps in sequence[/dim]\n"
            "  [cyan]A -> B, C -> D[/cyan]                "
            "[dim]\u2014 B and C in parallel[/dim]\n"
            "  [cyan]planner -> r1, r2 -> summarizer[/cyan] "
            "[dim]\u2014 fan-out + collect[/dim]"
        )
        console.print()
        console.print(make_panel(
            help_text, title="DSL syntax",
        ))
        console.print()
        console.print("[bold]Ready-made patterns:[/bold]")
        for name in PATTERNS:
            console.print(f"  [cyan]{name}[/cyan]: [dim]{PATTERNS[name]}[/dim]")
        console.print()
    else:
        click.echo("\nIn Binex, a workflow is a chain of agents connected by arrows (->).")
        click.echo("Agents on the same level (separated by commas) run in parallel.\n")
        click.echo("Examples:")
        click.echo("  A -> B -> C                      \u2014 three steps, one after another")
        click.echo(
            "  A -> B, C -> D"
            "                   \u2014 B and C run in parallel, D collects"
        )
        click.echo(
            "  planner -> r1, r2 -> summarizer"
            "  \u2014 plan, research in parallel, summarize\n"
        )
        click.echo("Ready-made patterns:")
        for name in PATTERNS:
            click.echo(f"  {name}: {PATTERNS[name]}")
        click.echo()

    dsl_input = click.prompt("Pick a pattern name OR write your own topology")

    if dsl_input in PATTERNS:
        dsl = PATTERNS[dsl_input]
    else:
        dsl = dsl_input
        try:
            parse_dsl([dsl])
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    _print_confirm("Custom workflow")
    _print_dsl_preview(dsl)
    return dsl


def _print_topology_preview_rich(levels: list[str]) -> None:
    """Print a styled Rich preview of the current topology."""
    from rich.text import Text

    from binex.cli.ui import get_console

    console = get_console(stderr=True)
    parts = " -> ".join(levels).replace(",", " ,").split()
    preview = Text("  Current graph: ", style="dim")
    for part in parts:
        ps = part.strip()
        if ps == "->":
            preview.append(" \u2192 ", style="dim")
        elif ps == ",":
            preview.append(", ", style="dim")
        else:
            preview.append(ps, style="bold magenta")
    console.print(preview)


def _step_mode_topology(*, input_fn=None) -> str:
    """Build workflow topology step by step. Returns DSL string like 'A -> B, C -> D'."""
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    levels: list[str] = []
    first = _prompt("Name the first node")
    levels.append(first.strip())

    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(f"  [dim]Current graph:[/dim] [bold magenta]{levels[0]}[/bold magenta]")

    while True:
        prev_display = levels[-1]
        answer = _prompt(f"Nodes after '{prev_display}'? (comma-separated, or 'done')")
        answer = answer.strip()
        if answer.lower() == "done":
            break
        levels.append(answer.strip())
        if has_rich():
            _print_topology_preview_rich(levels)

    return " -> ".join(levels)


def _step_user_input() -> bool:
    """Step 2: Ask whether to add a user prompt. Returns want_user_input."""
    _print_step(2, TOTAL_STEPS, "User input")

    add_user_input = click.prompt(
        "Start with a user prompt? (asks you a question before running)",
        default="y",
        type=click.Choice(["y", "n"], case_sensitive=False),
    )
    want_user_input = add_user_input.lower() == "y"
    if want_user_input:
        _print_confirm("User prompt will be added as the first step")
    else:
        _print_confirm("No user prompt")
    return want_user_input


def _step_project_name(default_name: str) -> tuple[str, Path]:
    """Step 4: Project name. Returns (project_name, project_dir)."""
    _print_step(4, TOTAL_STEPS, "Project name")
    project_name = click.prompt("Project name", default=default_name)

    try:
        project_dir = Path.cwd() / project_name
    except FileNotFoundError:
        click.echo(
            "Error: current directory does not exist. "
            "Please cd to a valid directory and try again.",
            err=True,
        )
        sys.exit(1)

    if project_dir.exists() and any(project_dir.iterdir()):
        click.echo(
            f"Error: directory '{project_name}' already exists and is not empty.",
            err=True,
        )
        sys.exit(1)

    return project_name, project_dir


def _step_generate_project(
    *,
    project_name: str,
    project_dir: Path,
    dsl: str,
    provider: ProviderConfig,
    model: str,
    api_key: str,
    want_user_input: bool,
    user_prompt_text: str,
) -> None:
    """Step 5: Generate project files and optionally run the workflow."""
    _print_step(5, TOTAL_STEPS, "Creating project")

    project_dir.mkdir(parents=True, exist_ok=True)

    workflow_yaml, needed_prompts = build_start_workflow(
        dsl=dsl,
        agent_prefix=provider.agent_prefix,
        model=model,
        user_input=want_user_input,
        user_prompt=user_prompt_text,
    )
    workflow_path = project_dir / "workflow.yaml"
    workflow_path.write_text(workflow_yaml)
    _print_file_created("workflow.yaml")

    if needed_prompts:
        _copy_prompts_to_project(project_dir, needed_prompts)
        _print_file_created(f"prompts/ ({len(needed_prompts)} files)")

    env_path = project_dir / ".env"
    env_content = f"{provider.env_var}={api_key}\n" if provider.env_var and api_key else ""
    env_path.write_text(env_content)
    _print_file_created(".env")

    gitignore_path = project_dir / ".gitignore"
    gitignore_path.write_text(".binex/\n.env\n__pycache__/\n*.pyc\n")
    _print_file_created(".gitignore")

    click.echo()

    run_now = click.prompt(
        "Run the workflow now?",
        default="y",
        type=click.Choice(["y", "n"], case_sensitive=False),
    )

    if run_now.lower() == "y":
        _run_workflow(str(workflow_path))
    else:
        _print_done_panel(project_name)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command("start", epilog="""\b
Examples:
  binex start   Launch the interactive wizard
""")
def start_cmd() -> None:
    """Interactive wizard to create and run an agent workflow."""
    _print_banner()

    dsl, default_name, user_prompt_text = _step_choose_template()
    want_user_input = _step_user_input()
    provider, model, api_key = _step_choose_provider()
    project_name, project_dir = _step_project_name(default_name)
    _step_generate_project(
        project_name=project_name,
        project_dir=project_dir,
        dsl=dsl,
        provider=provider,
        model=model,
        api_key=api_key,
        want_user_input=want_user_input,
        user_prompt_text=user_prompt_text,
    )
