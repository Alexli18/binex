"""CLI `binex start` — interactive wizard for creating agent workflows."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import yaml

from binex.cli.dsl_parser import PATTERNS, parse_dsl
from binex.cli.providers import PROVIDERS, ProviderConfig

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

# System prompts for common node roles — gives LLM agents meaningful instructions
_NODE_PROMPTS: dict[str, str] = {
    # Research pipeline
    "planner": (
        "You are a research planner. Given a topic, create a structured "
        "research plan with 3-5 specific subtopics or angles to investigate. "
        "Output a numbered list of research tasks."
    ),
    "researcher1": (
        "You are a thorough researcher. Investigate the assigned topic in depth. "
        "Provide detailed findings with specific facts, examples, and analysis. "
        "Focus on the first set of subtopics from the research plan."
    ),
    "researcher2": (
        "You are a thorough researcher. Investigate the assigned topic in depth. "
        "Provide detailed findings with specific facts, examples, and analysis. "
        "Focus on the second set of subtopics from the research plan."
    ),
    "validator": (
        "You are a research validator. Review the research findings for accuracy, "
        "completeness, and consistency. Identify gaps, contradictions, or areas "
        "needing more detail. Produce a consolidated, fact-checked summary."
    ),
    "summarizer": (
        "You are a summarizer. Create a clear, well-structured final summary "
        "of the validated research. Include key findings, conclusions, and "
        "actionable insights. Write in a professional, readable style."
    ),
    # Content review pipeline
    "draft": (
        "You are a content writer. Create a well-structured first draft "
        "based on the given topic or brief. Write clearly and engagingly."
    ),
    "review": (
        "You are an editor. Review the draft for clarity, accuracy, grammar, "
        "and style. Provide specific feedback and suggestions for improvement."
    ),
    "revise": (
        "You are a content writer. Revise the draft incorporating all editorial "
        "feedback. Improve clarity, fix issues, and polish the writing."
    ),
    "finalize": (
        "You are a final editor. Do a final quality check, ensure consistency, "
        "and produce the publication-ready version."
    ),
    # Data processing pipeline
    "splitter": (
        "You are a data analyst. Break the input into logical chunks "
        "that can be processed independently."
    ),
    "processor": (
        "You are a data processor. Analyze and transform the given data chunk. "
        "Extract key information and produce structured output."
    ),
    "merger": (
        "You are a data integrator. Combine all processed chunks into a single "
        "coherent result. Resolve any conflicts and produce a unified output."
    ),
    # Map-reduce pipeline
    "mapper": "You are a mapper. Process each input item independently.",
    "reducer": "You are a reducer. Combine all mapped results into a final output.",
    # Decision pipeline
    "approve": (
        "Review the draft and decide whether to approve or reject it. "
        "Explain your reasoning."
    ),
    "publish": (
        "You are a publisher. Take the approved content and prepare it "
        "for final output."
    ),
    # Generic fallbacks based on common name patterns
    "analyzer": (
        "You are an analyst. Examine the input carefully and provide "
        "a detailed analysis."
    ),
    "coordinator": (
        "You are a coordinator. Organize and delegate tasks based on the input."
    ),
    "reviewer": (
        "You are a reviewer. Evaluate the input for quality and correctness."
    ),
}

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
    # → should produce "llm://ollama/gemma3:4b", not "llm://ollama/ollama/gemma3:4b"
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

    for node_name in parsed.nodes:
        node_def: dict = {"agent": agent_uri, "outputs": ["result"]}
        # Assign system_prompt from known node roles
        prompt = _NODE_PROMPTS.get(node_name)
        if prompt:
            node_def["system_prompt"] = prompt
        deps = parsed.depends_on.get(node_name, [])
        if deps:
            node_def["depends_on"] = deps
        nodes[node_name] = node_def

    workflow = {
        "name": "start-wizard-workflow",
        "nodes": nodes,
    }
    return yaml.dump(workflow, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Run workflow (optional post-generation execution)
# ---------------------------------------------------------------------------

def _get_stores():
    """Create default stores. Extracted for test patching."""
    from binex.cli import get_stores
    return get_stores()


async def _execute(workflow_path: str) -> tuple:
    """Load and execute a workflow, returning (summary, errors, artifacts)."""
    from binex.adapters.local import LocalPythonAdapter
    from binex.models.artifact import Artifact, Lineage
    from binex.models.task import TaskNode
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
    ):
        counter[0] += 1
        click.echo(f"  [{counter[0]}/{total}] {node_id_} ...", err=True)
        await original_execute(
            spec_, dag_, scheduler_, run_id_, trace_id_,
            node_id_, node_artifacts_,
        )

    orch._execute_node = _progress_execute

    # Register adapters (mirrors run.py pattern)
    async def _default_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
        content = {a.id: a.content for a in inputs} if inputs else {"msg": "no input"}
        return [
            Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )
        ]

    for node in spec.nodes.values():
        agent = node.agent
        if agent in orch.dispatcher._adapters:
            continue
        if agent.startswith("local://"):
            orch.dispatcher.register_adapter(
                agent, LocalPythonAdapter(handler=_default_handler),
            )
        elif agent.startswith("llm://"):
            from binex.adapters.llm import LLMAdapter
            model_name = agent.removeprefix("llm://")
            config = node.config
            orch.dispatcher.register_adapter(
                agent,
                LLMAdapter(
                    model=model_name,
                    api_base=config.get("api_base"),
                    api_key=config.get("api_key"),
                    temperature=config.get("temperature"),
                    max_tokens=config.get("max_tokens"),
                ),
            )
        elif agent == "human://input":
            from binex.adapters.human import HumanInputAdapter
            orch.dispatcher.register_adapter(agent, HumanInputAdapter())
        elif agent.startswith("human://"):
            from binex.adapters.human import HumanApprovalAdapter
            orch.dispatcher.register_adapter(agent, HumanApprovalAdapter())
        elif agent.startswith("a2a://"):
            from binex.adapters.a2a import A2AAgentAdapter
            endpoint = agent.removeprefix("a2a://")
            orch.dispatcher.register_adapter(agent, A2AAgentAdapter(endpoint=endpoint))

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
        all_deps = {dep for node in spec.nodes.values() for dep in node.depends_on}
        terminal_nodes = [nid for nid in spec.nodes if nid not in all_deps]

        terminal_arts = [
            a for a in artifacts if a.lineage.produced_by in terminal_nodes
        ]
        if terminal_arts:
            try:
                from rich.console import Console
                from rich.markdown import Markdown
                from rich.panel import Panel

                console = Console()
                for art in terminal_arts:
                    content = art.content if art.content is not None else ""
                    if not isinstance(content, str):
                        import json as _json
                        content = _json.dumps(content, default=str, indent=2)
                    if len(content) > 4000:
                        content = content[:4000] + "..."
                    md = Markdown(content)
                    console.print(Panel(
                        md,
                        title=f"[bold]{art.lineage.produced_by}[/bold]",
                        subtitle=art.type,
                        border_style="green",
                    ))
            except ImportError:
                click.echo(f"\n{'── Result ':─<60}")
                for art in terminal_arts:
                    content = art.content
                    if isinstance(content, str) and len(content) > 2000:
                        content = content[:2000] + "..."
                    click.echo(f"[{art.lineage.produced_by}] {art.type}:")
                    click.echo(f"  {content}")


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command("start")
def start_cmd() -> None:
    """Interactive wizard to create and run an agent workflow."""
    click.echo("\nWelcome to Binex! Let's set up your agent network.\n")

    # --- Template selection ---
    click.echo("What would you like to build?")
    template_keys = list(TEMPLATES.keys())
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
        # Predefined template
        tpl_key = template_keys[choice - 1]
        tpl = TEMPLATES[tpl_key]
        dsl = PATTERNS[tpl["pattern"]]
        default_name = tpl["default_name"]
        user_prompt_text = tpl["prompt"]
    else:
        # Custom mode
        click.echo("\nIn Binex, a workflow is a chain of agents connected by arrows (->).")
        click.echo("Agents on the same level (separated by commas) run in parallel.\n")
        click.echo("Examples:")
        click.echo("  A -> B -> C                      \u2014 three steps, one after another")
        click.echo("  A -> B, C -> D                   \u2014 B and C run in parallel, D collects")
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
            # Validate DSL
            try:
                parse_dsl([dsl])
            except ValueError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)

        default_name = "my-project"
        user_prompt_text = "Enter your input:"

    # --- User input option ---
    add_user_input = click.prompt(
        "Start with a user prompt? (asks you a question before running)",
        default="y",
        type=click.Choice(["y", "n"], case_sensitive=False),
    )
    want_user_input = add_user_input.lower() == "y"

    # --- Provider selection ---
    click.echo("\nWhich LLM do you want to use?")
    top_providers = ["ollama", "openai", "anthropic"]
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
        # Show all providers
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

    # --- Model name ---
    model = click.prompt("Model", default=provider.default_model)

    # --- API key (paid providers only) ---
    api_key = ""
    if provider.env_var:
        api_key = click.prompt(provider.env_var)

    # --- Project name ---
    project_name = click.prompt("Project name", default=default_name)

    # --- Resolve absolute project path ---
    try:
        project_dir = Path.cwd() / project_name
    except FileNotFoundError:
        click.echo(
            "Error: current directory does not exist. "
            "Please cd to a valid directory and try again.",
            err=True,
        )
        sys.exit(1)

    # --- Directory collision check ---
    if project_dir.exists() and any(project_dir.iterdir()):
        click.echo(
            f"Error: directory '{project_name}' already exists and is not empty.",
            err=True,
        )
        sys.exit(1)

    # --- Generate project ---
    click.echo(f"\nCreating project in ./{project_name}...")
    project_dir.mkdir(parents=True, exist_ok=True)

    # workflow.yaml
    workflow_yaml = build_start_workflow(
        dsl=dsl,
        agent_prefix=provider.agent_prefix,
        model=model,
        user_input=want_user_input,
        user_prompt=user_prompt_text,
    )
    workflow_path = project_dir / "workflow.yaml"
    workflow_path.write_text(workflow_yaml)
    click.echo("  workflow.yaml")

    # .env
    env_path = project_dir / ".env"
    env_content = f"{provider.env_var}={api_key}\n" if provider.env_var and api_key else ""
    env_path.write_text(env_content)
    click.echo("  .env")

    # .gitignore
    gitignore_path = project_dir / ".gitignore"
    gitignore_path.write_text(".binex/\n.env\n__pycache__/\n*.pyc\n")
    click.echo("  .gitignore")

    # --- Run now? ---
    run_now = click.prompt(
        "Run the workflow now?",
        default="y",
        type=click.Choice(["y", "n"], case_sensitive=False),
    )

    if run_now.lower() == "y":
        _run_workflow(str(workflow_path))
    else:
        click.echo(f"\nDone! Your project is saved in ./{project_name}/\n")
        click.echo("Next steps:")
        click.echo(f"  cd {project_name}")
        click.echo("  binex run workflow.yaml                \u2014 run your workflow")
        click.echo("  code workflow.yaml                     \u2014 edit your workflow")
