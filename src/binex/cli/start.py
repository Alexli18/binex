"""CLI `binex start` — interactive wizard for creating agent workflows."""

from __future__ import annotations

import asyncio
import importlib.resources
import shutil
import sys
from pathlib import Path

import click
import yaml

from binex.cli import has_rich
from binex.cli.dsl_parser import PATTERNS, parse_dsl
from binex.cli.providers import PROVIDERS, ProviderConfig

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

# Maps node names to prompt .md filenames in binex/prompts/
_NODE_PROMPT_FILES: dict[str, str] = {
    # Research pipeline
    "planner": "research-planner.md",
    "researcher1": "researcher.md",
    "researcher2": "researcher.md",
    "validator": "research-validator.md",
    "summarizer": "research-synthesizer.md",
    # Content review pipeline
    "draft": "draft-writer.md",
    "review": "content-reviewer.md",
    "revise": "content-reviser.md",
    "finalize": "content-editor.md",
    # Data processing pipeline
    "splitter": "chunk-splitter.md",
    "processor": "chunk-processor.md",
    "merger": "chunk-merger.md",
    # Map-reduce pipeline
    "mapper": "data-processor.md",
    "reducer": "data-aggregator.md",
    # Generic fallbacks
    "analyzer": "data-refiner.md",
    "reviewer": "content-reviewer.md",
}


def _get_prompts_dir() -> Path:
    """Resolve the bundled prompts directory (src/binex/prompts/)."""
    ref = importlib.resources.files("binex") / "prompts"
    return Path(str(ref))


def _copy_prompts_to_project(
    project_dir: Path,
    needed_files: set[str],
) -> None:
    """Copy needed prompt .md files into project_dir/prompts/."""
    src_dir = _get_prompts_dir()
    dst_dir = project_dir / "prompts"
    dst_dir.mkdir(exist_ok=True)
    for filename in sorted(needed_files):
        src = src_dir / filename
        if src.exists():
            shutil.copy2(src, dst_dir / filename)

TEMPLATES: dict[str, dict[str, str]] = {
    "research": {
        "label": "Research pipeline",
        "description": "plan, research, summarize a topic",
        "pattern": "research",
        "prompt": "What would you like to research?",
        "default_name": "my-research-pipeline",
    },
    "content-review": {
        "label": "Content review",
        "description": "draft, review, revise, finalize",
        "pattern": "chain-with-review",
        "prompt": "What content would you like to create?",
        "default_name": "my-content-review",
    },
    "data-processing": {
        "label": "Data processing",
        "description": "split work, process in parallel, merge results",
        "pattern": "map-reduce",
        "prompt": "What data would you like to process?",
        "default_name": "my-data-pipeline",
    },
    "decision": {
        "label": "Decision pipeline",
        "description": "analyze, get human approval, execute",
        "pattern": "human-approval",
        "prompt": "What decision do you need to make?",
        "default_name": "my-decision-pipeline",
    },
}

# Template icons for visual flair
_TEMPLATE_ICONS: dict[str, str] = {
    "research": "\U0001f50d",
    "content-review": "\U0001f4dd",
    "data-processing": "\u2699\ufe0f",
    "decision": "\u2696\ufe0f",
}


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    """Print a welcome banner."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        title = Text()
        title.append("Welcome to ", style="bold")
        title.append("Binex", style="bold cyan")
        title.append("!", style="bold")
        subtitle = Text("Let's set up your agent network.", style="dim")
        content = Text.assemble(title, "\n", subtitle)
        console.print()
        console.print(make_panel(content))
        console.print()
    else:
        click.echo("\nWelcome to Binex! Let's set up your agent network.\n")


def _print_step(step: int, total: int, label: str) -> None:
    """Print a step header."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        header = Text()
        header.append(f"Step {step} of {total}", style="bold cyan")
        header.append(f" \u00b7 {label}", style="bold")
        console.print(header)
    else:
        click.echo(f"\nStep {step} of {total} \u00b7 {label}", err=True)


def _print_confirm(message: str) -> None:
    """Print a confirmation/success message."""
    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(f"  [green]\u2713[/green] {message}")
    else:
        click.echo(f"  \u2713 {message}", err=True)


def _print_dsl_preview(dsl: str) -> None:
    """Print a visual preview of the workflow DAG."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        preview = Text()
        preview.append("  Pipeline: ", style="dim")
        # Color node names cyan and arrows dim
        parts = dsl.replace(",", " ,").split()
        for part in parts:
            part_stripped = part.strip()
            if part_stripped == "->":
                preview.append(" \u2192 ", style="dim")
            elif part_stripped == ",":
                preview.append(", ", style="dim")
            else:
                preview.append(part_stripped, style="bold magenta")
        console.print(preview)
        console.print()
    else:
        click.echo(f"  Pipeline: {dsl}\n", err=True)


def _print_file_created(filename: str) -> None:
    """Print a file creation confirmation."""
    if has_rich():
        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        console.print(f"  [green]\u2713[/green] [bold]{filename}[/bold]")
    else:
        click.echo(f"  \u2713 {filename}", err=True)


def _print_done_panel(project_name: str) -> None:
    """Print a completion panel with next steps."""
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        content = Text()
        content.append(f"Project saved in ./{project_name}/\n\n", style="bold green")
        content.append("Next steps:\n", style="bold")
        content.append(f"  cd {project_name}\n", style="cyan")
        content.append("  binex run workflow.yaml", style="cyan")
        content.append("    \u2014 run your workflow\n", style="dim")
        content.append("  code workflow.yaml", style="cyan")
        content.append("         \u2014 edit your workflow", style="dim")
        console.print()
        console.print(make_panel(content, title="Done!"))
    else:
        click.echo(f"\nDone! Your project is saved in ./{project_name}/\n")
        click.echo("Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  binex run workflow.yaml                \u2014 run your workflow")
        click.echo("  code workflow.yaml                     \u2014 edit your workflow")


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
        accumulated_cost_=0.0,
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
            node_id_, node_artifacts_, accumulated_cost_,
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
# Wizard steps
# ---------------------------------------------------------------------------

TOTAL_STEPS = 5


def _step_choose_template() -> tuple[str, str, str]:
    """Step 1: Template selection. Returns (dsl, default_name, user_prompt_text)."""
    _print_step(1, TOTAL_STEPS, "Choose a template")
    click.echo()

    template_keys = list(TEMPLATES.keys())
    if has_rich():
        from rich.text import Text

        from binex.cli.ui import get_console

        console = get_console(stderr=True)
        for i, key in enumerate(template_keys, 1):
            t = TEMPLATES[key]
            icon = _TEMPLATE_ICONS.get(key, "\u2022")
            line = Text()
            line.append(f"  {i}) ", style="dim")
            line.append(f"{icon} {t['label']:20s}", style="bold")
            line.append(f" \u2014 {t['description']}", style="dim")
            console.print(line)
        custom_n = len(template_keys) + 1
        line = Text()
        line.append(f"  {custom_n}) ", style="dim")
        line.append(f"\U0001f527 {'Custom':20s}", style="bold")
        line.append(" \u2014 build your own workflow with arrows", style="dim")
        console.print(line)
    else:
        for i, key in enumerate(template_keys, 1):
            t = TEMPLATES[key]
            click.echo(f"  {i}) {t['label']:20s} \u2014 {t['description']}")
        custom_n = len(template_keys) + 1
        click.echo(f"  {custom_n}) {'Custom':20s} \u2014 build your own workflow with arrows")
    click.echo()

    choice = click.prompt("Choose", default=1, type=int)

    if choice < 1 or choice > len(template_keys) + 1:
        click.echo(f"Error: invalid choice {choice}.", err=True)
        sys.exit(1)

    if choice <= len(template_keys):
        tpl_key = template_keys[choice - 1]
        tpl = TEMPLATES[tpl_key]
        dsl = PATTERNS[tpl["pattern"]]
        _print_confirm(f"{tpl['label']}")
        _print_dsl_preview(dsl)
        return dsl, tpl["default_name"], tpl["prompt"]

    # Custom mode
    return _step_custom_template()


def _step_custom_template() -> tuple[str, str, str]:
    """Custom template sub-step: show DSL help, get user topology."""
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
    return dsl, "my-project", "Enter your input:"


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


def _step_choose_provider() -> tuple[ProviderConfig, str, str]:
    """Step 3: Provider selection. Returns (provider, model, api_key)."""
    _print_step(3, TOTAL_STEPS, "Choose your LLM")
    click.echo()

    top_providers = ["ollama", "openai", "anthropic"]
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
    click.echo()

    prov_choice = click.prompt("Choose", default=1, type=int)

    if prov_choice < 1 or prov_choice > len(top_providers) + 1:
        click.echo(f"Error: invalid choice {prov_choice}.", err=True)
        sys.exit(1)

    if prov_choice <= len(top_providers):
        provider: ProviderConfig = PROVIDERS[top_providers[prov_choice - 1]]
    else:
        all_names = list(PROVIDERS.keys())
        click.echo("\nAll providers:")
        for i, pname in enumerate(all_names, 1):
            click.echo(f"  {i}) {pname}")
        click.echo()
        sub_choice = click.prompt("Choose", type=int)
        if sub_choice < 1 or sub_choice > len(all_names):
            click.echo(f"Error: invalid choice {sub_choice}.", err=True)
            sys.exit(1)
        provider = PROVIDERS[all_names[sub_choice - 1]]

    model = click.prompt("Model", default=provider.default_model)
    _print_confirm(f"{provider.name} / {model}")

    api_key = ""
    if provider.env_var:
        api_key = click.prompt(provider.env_var)

    return provider, model, api_key


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
