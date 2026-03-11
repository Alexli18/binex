# Custom Workflow Wizard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the "Custom (DSL only)" option in `binex start` with a full interactive wizard that lets users build custom workflows with per-node configuration (agent type, provider, prompts, back-edges, advanced params).

**Architecture:** Three-phase wizard inside existing `src/binex/cli/start.py`. Phase 1 collects topology (DSL or step-by-step). Phase 2 configures each node interactively. Phase 3 previews YAML, saves files, optionally runs. New function `build_custom_workflow()` generates YAML from per-node config dicts instead of uniform DSL+provider.

**Tech Stack:** Python 3.11+, click (CLI prompts), PyYAML (generation), rich (optional styled output)

---

### Task 1: Step-mode topology builder

**Files:**
- Modify: `src/binex/cli/start.py:429-489` (replace `_step_custom_template`)
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
"""Tests for custom workflow wizard in `binex start`."""

from __future__ import annotations

import yaml

from binex.cli.start import _step_mode_topology


class TestStepModeTopology:
    """Step-by-step topology builder."""

    def test_simple_linear(self):
        """Three nodes in sequence."""
        # Simulates: "planner" -> "researcher" -> "writer" -> "done"
        inputs = iter(["planner", "researcher", "writer", "done"])
        result = _step_mode_topology(input_fn=lambda prompt: next(inputs))
        assert result == "planner -> researcher -> writer"

    def test_parallel_nodes(self):
        """Fan-out: one node followed by two parallel."""
        inputs = iter(["start", "a, b", "end", "done"])
        result = _step_mode_topology(input_fn=lambda prompt: next(inputs))
        assert result == "start -> a, b -> end"

    def test_single_node(self):
        """Only one node then done."""
        inputs = iter(["solo", "done"])
        result = _step_mode_topology(input_fn=lambda prompt: next(inputs))
        assert result == "solo"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestStepModeTopology -v`
Expected: FAIL with `ImportError: cannot import name '_step_mode_topology'`

**Step 3: Implement `_step_mode_topology`**

Add to `src/binex/cli/start.py` after `_step_custom_template` (around line 489):

```python
def _step_mode_topology(*, input_fn=None) -> str:
    """Build workflow topology step by step.

    Returns a DSL string like 'A -> B, C -> D'.
    If input_fn is provided, uses it instead of click.prompt (for testing).
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    levels: list[str] = []
    first = _prompt("Name the first node")
    levels.append(first.strip())

    while True:
        prev_display = levels[-1]
        answer = _prompt(
            f"Nodes after '{prev_display}'? (comma-separated, or 'done')"
        )
        answer = answer.strip()
        if answer.lower() == "done":
            break
        levels.append(answer.strip())

    return " -> ".join(levels)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestStepModeTopology -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add step-mode topology builder for custom wizard"
```

---

### Task 2: Update `_step_custom_template` to offer DSL vs step mode

**Files:**
- Modify: `src/binex/cli/start.py:429-489` (`_step_custom_template`)
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

Add to `tests/unit/test_custom_wizard.py`:

```python
from unittest.mock import patch
from click.testing import CliRunner
from binex.cli.start import start_cmd


class TestCustomTemplateHybrid:
    """Custom template offers DSL or step mode."""

    def test_dsl_mode_still_works(self, tmp_path, monkeypatch):
        """Entering DSL directly works as before."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=5, mode=dsl, topology="X -> Y", user_input=n, ollama, default, name, run=n
        result = runner.invoke(
            start_cmd,
            input="5\ndsl\nX -> Y\nn\n1\n\nhybrid-dsl\nn\n",
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "hybrid-dsl" / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"X", "Y"}

    def test_step_mode_works(self, tmp_path, monkeypatch):
        """Choosing 'step' launches interactive builder."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # custom=5, mode=step, nodes: A -> B -> done, user_input=n, ollama, default, name, run=n
        result = runner.invoke(
            start_cmd,
            input="5\nstep\nA\nB\ndone\nn\n1\n\nhybrid-step\nn\n",
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "hybrid-step" / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"A", "B"}
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestCustomTemplateHybrid -v`
Expected: FAIL (current code doesn't ask dsl/step)

**Step 3: Update `_step_custom_template`**

Replace the function body in `src/binex/cli/start.py`:

```python
def _step_custom_template() -> tuple[str, str, str]:
    """Custom template sub-step: DSL or step-by-step topology builder."""
    if has_rich():
        from binex.cli.ui import get_console
        console = get_console(stderr=True)
        console.print()
        console.print("  [bold]1)[/bold] [cyan]DSL[/cyan] — write topology as arrows (e.g. A -> B, C -> D)")
        console.print("  [bold]2)[/bold] [cyan]Step-by-step[/cyan] — build nodes one at a time")
        console.print()
    else:
        click.echo()
        click.echo("  1) DSL — write topology as arrows (e.g. A -> B, C -> D)")
        click.echo("  2) Step-by-step — build nodes one at a time")
        click.echo()

    mode = click.prompt("Choose mode", type=click.Choice(["1", "2"]), default="1")

    if mode == "1":
        return _step_custom_dsl()
    else:
        dsl = _step_mode_topology()
        _print_confirm("Custom workflow")
        _print_dsl_preview(dsl)
        return dsl, "my-project", "Enter your input:"


def _step_custom_dsl() -> tuple[str, str, str]:
    """DSL sub-mode: show syntax help, get topology string."""
    # Move the existing DSL help/input code here (the Rich panel, examples, patterns list)
    # ... existing code from current _step_custom_template ...
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
        console.print(make_panel(help_text, title="DSL syntax"))
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
        click.echo("  A -> B, C -> D                   \u2014 B and C run in parallel, D collects")
        click.echo("  planner -> r1, r2 -> summarizer  \u2014 plan, research in parallel, summarize\n")
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
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestCustomTemplateHybrid -v`
Expected: PASS

Also run existing tests to ensure no regression:
Run: `pytest tests/unit/test_cli_start.py -v`

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): offer DSL or step-by-step mode in custom template"
```

---

### Task 3: Prompt selection helper

**Files:**
- Modify: `src/binex/cli/start.py`
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
from binex.cli.start import _select_prompt, _get_bundled_prompt_list


class TestPromptSelection:
    """Prompt picker: bundled list + custom text + file path."""

    def test_get_bundled_prompt_list(self):
        """Should return list of (filename, first_line) tuples."""
        prompts = _get_bundled_prompt_list()
        assert len(prompts) == 14
        assert all(isinstance(p, tuple) and len(p) == 2 for p in prompts)

    def test_select_bundled_prompt(self):
        """Choosing a number selects bundled prompt as file:// reference."""
        prompts = _get_bundled_prompt_list()
        # Select first bundled prompt (choice "1")
        result = _select_prompt(
            node_id="test",
            input_fn=lambda prompt: "1",
        )
        assert result.startswith("file://prompts/")
        assert result.endswith(".md")

    def test_select_custom_text(self):
        """Choosing 'custom text' option returns entered text."""
        prompts = _get_bundled_prompt_list()
        custom_option = str(len(prompts) + 1)
        inputs = iter([custom_option, "You are a helpful bot"])
        result = _select_prompt(
            node_id="test",
            input_fn=lambda prompt: next(inputs),
        )
        assert result == "You are a helpful bot"

    def test_select_file_path(self):
        """Choosing 'file path' option returns file:// reference."""
        prompts = _get_bundled_prompt_list()
        file_option = str(len(prompts) + 2)
        inputs = iter([file_option, "/path/to/my-prompt.md"])
        result = _select_prompt(
            node_id="test",
            input_fn=lambda prompt: next(inputs),
        )
        assert result == "file:///path/to/my-prompt.md"

    def test_matching_node_name_marked_recommended(self):
        """When node_id matches a bundled prompt name, it should appear in output."""
        # This is a visual feature — test that the function still returns correct result
        result = _select_prompt(
            node_id="researcher",
            input_fn=lambda prompt: "1",
        )
        assert result.startswith("file://prompts/")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestPromptSelection -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

Add to `src/binex/cli/start.py`:

```python
def _get_bundled_prompt_list() -> list[tuple[str, str]]:
    """Return list of (filename, description) for bundled prompts."""
    prompts_dir = _get_prompts_dir()
    result = []
    for md_file in sorted(prompts_dir.glob("*.md")):
        first_line = md_file.read_text().strip().split("\n")[0][:60]
        result.append((md_file.name, first_line))
    return result


def _select_prompt(*, node_id: str, input_fn=None) -> str:
    """Interactive prompt picker. Returns system_prompt string.

    Options: bundled prompts (file:// ref), custom text, file path.
    If input_fn is provided, uses it instead of click.prompt (for testing).
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))
    bundled = _get_bundled_prompt_list()

    # Find recommended prompt (node name matches filename stem)
    recommended_idx = None
    for i, (filename, _desc) in enumerate(bundled):
        stem = filename.removesuffix(".md")
        if stem == node_id or node_id in stem or stem in node_id:
            recommended_idx = i
            break

    click.echo("  System prompt:")
    for i, (filename, desc) in enumerate(bundled, 1):
        tag = " (recommended)" if i - 1 == recommended_idx else ""
        click.echo(f"    {i}) {filename}{tag} — {desc}")

    custom_text_n = len(bundled) + 1
    file_path_n = len(bundled) + 2
    click.echo(f"    {custom_text_n}) Write custom text")
    click.echo(f"    {file_path_n}) Provide file path")

    choice = _prompt("Choose prompt")

    choice_int = int(choice)
    if choice_int <= len(bundled):
        filename = bundled[choice_int - 1][0]
        return f"file://prompts/{filename}"
    elif choice_int == custom_text_n:
        text = _prompt("Enter system prompt text")
        return text
    else:
        path = _prompt("Enter path to prompt file")
        if not path.startswith("file://"):
            path = f"file://{path}"
        return path
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestPromptSelection -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add prompt selection helper with bundled/custom/file options"
```

---

### Task 4: Node configuration function

**Files:**
- Modify: `src/binex/cli/start.py`
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
from binex.cli.start import _configure_node


class TestConfigureNode:
    """Per-node interactive configuration."""

    def test_llm_node_basic(self):
        """LLM node returns agent URI, prompt, no back-edge."""
        inputs = iter([
            "1",          # agent type: LLM
            "1",          # provider: ollama
            "",           # model: default
            "1",          # prompt: first bundled
            "n",          # back-edge: no
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="writer",
            dependencies=["planner"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"].startswith("llm://")
        assert config["system_prompt"].startswith("file://prompts/")
        assert "back_edge" not in config
        assert config["depends_on"] == ["planner"]

    def test_human_review_node(self):
        """Human review node uses human://review agent."""
        inputs = iter([
            "2",          # agent type: Human review
            "n",          # back-edge: no
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="review",
            dependencies=["writer"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"] == "human://review"
        assert "system_prompt" not in config or config.get("system_prompt") is None

    def test_human_input_node(self):
        """Human input node uses human://input agent."""
        inputs = iter([
            "3",          # agent type: Human input
            "What is your topic?",  # prompt text
            "n",          # back-edge: no
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="ask",
            dependencies=[],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"] == "human://input"
        assert config["system_prompt"] == "What is your topic?"

    def test_a2a_node(self):
        """A2A node uses a2a:// agent."""
        inputs = iter([
            "4",                          # agent type: A2A
            "http://localhost:9000",       # endpoint
            "n",                          # back-edge: no
            "n",                          # advanced: no
        ])
        config = _configure_node(
            node_id="external",
            dependencies=["planner"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["agent"] == "a2a://http://localhost:9000"

    def test_back_edge_config(self):
        """Human review node with back-edge."""
        inputs = iter([
            "2",          # agent type: Human review
            "y",          # back-edge: yes
            "1",          # target: first upstream node (writer)
            "3",          # max_iterations
            "n",          # advanced: no
        ])
        config = _configure_node(
            node_id="review",
            dependencies=["writer"],
            input_fn=lambda prompt: next(inputs),
        )
        assert config["back_edge"]["target"] == "writer"
        assert config["back_edge"]["max_iterations"] == 3
        assert "rejected" in config["back_edge"]["when"]
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestConfigureNode -v`
Expected: FAIL with `ImportError`

**Step 3: Implement `_configure_node`**

Add to `src/binex/cli/start.py`:

```python
def _configure_node(
    *,
    node_id: str,
    dependencies: list[str],
    input_fn=None,
) -> dict:
    """Interactively configure a single node. Returns a dict for YAML generation.

    Keys: agent, system_prompt, depends_on, back_edge, outputs,
    plus optional: budget, retry_policy, deadline_ms, config.
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    click.echo(f"\n  Agent type for '{node_id}':")
    click.echo("    1) LLM (language model)")
    click.echo("    2) Human review (approve/reject)")
    click.echo("    3) Human input (free text)")
    click.echo("    4) A2A (external agent)")
    agent_type = _prompt("Choose")

    config: dict = {"outputs": ["result"]}
    if dependencies:
        config["depends_on"] = dependencies

    if agent_type == "1":
        # LLM — provider + model + prompt
        provider, model = _select_provider(input_fn=_prompt)
        config["agent"] = f"{provider.agent_prefix}{model}"
        config["system_prompt"] = _select_prompt(node_id=node_id, input_fn=_prompt)
    elif agent_type == "2":
        # Human review
        config["agent"] = "human://review"
    elif agent_type == "3":
        # Human input
        config["agent"] = "human://input"
        config["system_prompt"] = _prompt("Prompt text for user")
    elif agent_type == "4":
        # A2A
        endpoint = _prompt("Endpoint URL")
        config["agent"] = f"a2a://{endpoint}"
    else:
        click.echo(f"Error: invalid choice '{agent_type}'", err=True)
        sys.exit(1)

    # Back-edge (offer for human review nodes, but allow for any)
    add_back_edge = _prompt("Add review loop (back-edge)? (y/n)")
    if add_back_edge.lower() == "y":
        config["back_edge"] = _configure_back_edge(
            node_id=node_id,
            upstream_nodes=dependencies,
            input_fn=_prompt,
        )

    # Advanced params
    add_advanced = _prompt("Configure advanced parameters? (y/n)")
    if add_advanced.lower() == "y":
        advanced = _configure_advanced_params(input_fn=_prompt)
        config.update(advanced)

    return config


def _select_provider(*, input_fn=None) -> tuple[ProviderConfig, str]:
    """Select provider and model. Returns (ProviderConfig, model_string)."""
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

    provider_names = list(PROVIDERS.keys())
    click.echo("  Provider:")
    for i, name in enumerate(provider_names, 1):
        p = PROVIDERS[name]
        suffix = "free, local" if p.env_var is None else "API key required"
        click.echo(f"    {i}) {name} — {suffix}")

    choice = int(_prompt("Choose provider"))
    provider = PROVIDERS[provider_names[choice - 1]]
    model = _prompt(f"Model [{provider.default_model}]") or provider.default_model
    if not model:
        model = provider.default_model

    # Deduplicate provider prefix in model name
    prefix_provider = provider.agent_prefix.split("://")[-1].rstrip("/")
    if prefix_provider and model.startswith(f"{prefix_provider}/"):
        model = model[len(prefix_provider) + 1:]

    return provider, model
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestConfigureNode -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add per-node interactive configuration"
```

---

### Task 5: Advanced parameters configuration

**Files:**
- Modify: `src/binex/cli/start.py`
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
from binex.cli.start import _configure_advanced_params


class TestAdvancedParams:
    """Optional advanced parameter configuration."""

    def test_budget_only(self):
        inputs = iter(["0.50", "", "", ""])
        result = _configure_advanced_params(input_fn=lambda prompt: next(inputs))
        assert result["budget"] == {"max_cost": 0.50}
        assert "retry_policy" not in result
        assert "deadline_ms" not in result
        assert "config" not in result

    def test_all_params(self):
        inputs = iter([
            "1.00",         # budget max_cost
            "3",            # retry max_retries
            "exponential",  # retry backoff
            "30",           # deadline seconds
            "0.7",          # temperature
            "2000",         # max_tokens
        ])
        result = _configure_advanced_params(input_fn=lambda prompt: next(inputs))
        assert result["budget"] == {"max_cost": 1.00}
        assert result["retry_policy"] == {"max_retries": 3, "backoff": "exponential"}
        assert result["deadline_ms"] == 30000
        assert result["config"] == {"temperature": 0.7, "max_tokens": 2000}

    def test_skip_all(self):
        """Empty inputs skip all optional params."""
        inputs = iter(["", "", "", ""])
        result = _configure_advanced_params(input_fn=lambda prompt: next(inputs))
        assert result == {}
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestAdvancedParams -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

```python
def _configure_advanced_params(*, input_fn=None) -> dict:
    """Collect optional advanced parameters. Returns dict of extra YAML keys.

    Empty input skips each parameter.
    """
    _prompt = input_fn or (lambda prompt: click.prompt(prompt, default=""))
    result: dict = {}

    # Budget
    budget_str = _prompt("Budget max_cost in $ (empty to skip)")
    if budget_str:
        result["budget"] = {"max_cost": float(budget_str)}

    # Retry
    retry_str = _prompt("Max retries (empty to skip)")
    if retry_str:
        backoff = _prompt("Backoff strategy [fixed/exponential]") or "exponential"
        result["retry_policy"] = {
            "max_retries": int(retry_str),
            "backoff": backoff,
        }

    # Deadline
    deadline_str = _prompt("Deadline in seconds (empty to skip)")
    if deadline_str:
        result["deadline_ms"] = int(float(deadline_str) * 1000)

    # Config (temperature, max_tokens)
    temp_str = _prompt("Temperature (empty to skip)")
    config: dict = {}
    if temp_str:
        config["temperature"] = float(temp_str)
    tokens_str = _prompt("Max tokens (empty to skip)")
    if tokens_str:
        config["max_tokens"] = int(tokens_str)
    if config:
        result["config"] = config

    return result
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestAdvancedParams -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add advanced params config (budget, retry, deadline, config)"
```

---

### Task 6: Back-edge configuration helper

**Files:**
- Modify: `src/binex/cli/start.py`
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
from binex.cli.start import _configure_back_edge


class TestConfigureBackEdge:
    """Back-edge (review loop) configuration."""

    def test_basic_back_edge(self):
        inputs = iter(["1", "3"])  # target choice=1 (writer), max_iterations=3
        result = _configure_back_edge(
            node_id="review",
            upstream_nodes=["writer"],
            input_fn=lambda prompt: next(inputs),
        )
        assert result["target"] == "writer"
        assert result["when"] == "${review.decision} == rejected"
        assert result["max_iterations"] == 3

    def test_multiple_upstream_choice(self):
        inputs = iter(["2", "5"])  # target=2nd upstream (researcher), max=5
        result = _configure_back_edge(
            node_id="review",
            upstream_nodes=["writer", "researcher"],
            input_fn=lambda prompt: next(inputs),
        )
        assert result["target"] == "researcher"
        assert result["max_iterations"] == 5

    def test_default_max_iterations(self):
        inputs = iter(["1", ""])  # target, empty=default
        result = _configure_back_edge(
            node_id="review",
            upstream_nodes=["generate"],
            input_fn=lambda prompt: next(inputs),
        )
        assert result["max_iterations"] == 3
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestConfigureBackEdge -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

```python
def _configure_back_edge(
    *,
    node_id: str,
    upstream_nodes: list[str],
    input_fn=None,
) -> dict:
    """Configure a back-edge for review loops. Returns back_edge dict."""
    _prompt = input_fn or (lambda prompt: click.prompt(prompt))

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
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestConfigureBackEdge -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add back-edge configuration helper"
```

---

### Task 7: `build_custom_workflow` — YAML generator from per-node configs

**Files:**
- Modify: `src/binex/cli/start.py`
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
from binex.cli.start import build_custom_workflow


class TestBuildCustomWorkflow:
    """Generate YAML from per-node config dicts."""

    def test_simple_two_nodes(self):
        configs = {
            "planner": {
                "agent": "llm://ollama/llama3.2",
                "system_prompt": "file://prompts/research-planner.md",
                "outputs": ["result"],
            },
            "writer": {
                "agent": "llm://ollama/llama3.2",
                "system_prompt": "You are a writer",
                "outputs": ["result"],
                "depends_on": ["planner"],
            },
        }
        yaml_str, needed = build_custom_workflow(
            name="test-wf", nodes_config=configs,
        )
        data = yaml.safe_load(yaml_str)
        assert data["name"] == "test-wf"
        assert set(data["nodes"].keys()) == {"planner", "writer"}
        assert data["nodes"]["writer"]["depends_on"] == ["planner"]
        assert "research-planner.md" in needed

    def test_back_edge_included(self):
        configs = {
            "generate": {
                "agent": "llm://ollama/llama3.2",
                "outputs": ["result"],
            },
            "review": {
                "agent": "human://review",
                "outputs": ["result"],
                "depends_on": ["generate"],
                "back_edge": {
                    "target": "generate",
                    "when": "${review.decision} == rejected",
                    "max_iterations": 3,
                },
            },
        }
        yaml_str, _ = build_custom_workflow(name="be-wf", nodes_config=configs)
        data = yaml.safe_load(yaml_str)
        assert "back_edge" in data["nodes"]["review"]
        assert data["nodes"]["review"]["back_edge"]["target"] == "generate"

    def test_advanced_params_included(self):
        configs = {
            "node1": {
                "agent": "llm://openai/gpt-4o",
                "outputs": ["result"],
                "budget": {"max_cost": 0.50},
                "retry_policy": {"max_retries": 2, "backoff": "fixed"},
                "deadline_ms": 30000,
                "config": {"temperature": 0.7},
            },
        }
        yaml_str, _ = build_custom_workflow(name="adv-wf", nodes_config=configs)
        data = yaml.safe_load(yaml_str)
        node = data["nodes"]["node1"]
        assert node["budget"]["max_cost"] == 0.50
        assert node["retry_policy"]["max_retries"] == 2
        assert node["deadline_ms"] == 30000
        assert node["config"]["temperature"] == 0.7

    def test_no_none_values_in_output(self):
        """None values should not appear in generated YAML."""
        configs = {
            "review": {
                "agent": "human://review",
                "outputs": ["result"],
                "system_prompt": None,
            },
        }
        yaml_str, _ = build_custom_workflow(name="clean", nodes_config=configs)
        assert "null" not in yaml_str
        assert "None" not in yaml_str
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestBuildCustomWorkflow -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

```python
def build_custom_workflow(
    *,
    name: str,
    nodes_config: dict[str, dict],
) -> tuple[str, set[str]]:
    """Generate workflow YAML from per-node configuration dicts.

    Returns (yaml_string, set_of_needed_prompt_files).
    """
    needed_prompts: set[str] = set()
    nodes: dict[str, dict] = {}

    for node_id, cfg in nodes_config.items():
        node: dict = {}
        node["agent"] = cfg["agent"]

        if cfg.get("system_prompt"):
            node["system_prompt"] = cfg["system_prompt"]
            # Track bundled prompt files
            sp = cfg["system_prompt"]
            if sp.startswith("file://prompts/") and sp.endswith(".md"):
                needed_prompts.add(sp.removeprefix("file://prompts/"))

        node["outputs"] = cfg.get("outputs", ["result"])

        if cfg.get("depends_on"):
            node["depends_on"] = cfg["depends_on"]

        if cfg.get("back_edge"):
            node["back_edge"] = cfg["back_edge"]

        if cfg.get("budget"):
            node["budget"] = cfg["budget"]

        if cfg.get("retry_policy"):
            node["retry_policy"] = cfg["retry_policy"]

        if cfg.get("deadline_ms"):
            node["deadline_ms"] = cfg["deadline_ms"]

        if cfg.get("config"):
            node["config"] = cfg["config"]

        nodes[node_id] = node

    workflow = {"name": name, "nodes": nodes}
    yaml_str = yaml.dump(workflow, default_flow_style=False, sort_keys=False)
    return yaml_str, needed_prompts
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestBuildCustomWorkflow -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add build_custom_workflow YAML generator"
```

---

### Task 8: YAML preview with Rich highlighting

**Files:**
- Modify: `src/binex/cli/start.py`
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
from binex.cli.start import _preview_yaml


class TestPreviewYaml:
    """YAML preview display."""

    def test_preview_returns_without_error(self):
        """Preview should not raise for valid YAML."""
        yaml_content = "name: test\nnodes:\n  a:\n    agent: llm://test\n"
        # Should not raise
        _preview_yaml(yaml_content)

    def test_preview_with_empty_yaml(self):
        """Edge case: empty string."""
        _preview_yaml("")
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestPreviewYaml -v`
Expected: FAIL with `ImportError`

**Step 3: Implement**

```python
def _preview_yaml(yaml_content: str) -> None:
    """Display YAML content with syntax highlighting if Rich is available."""
    if has_rich():
        from rich.syntax import Syntax

        from binex.cli.ui import get_console, make_panel

        console = get_console(stderr=True)
        syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=False)
        console.print()
        console.print(make_panel(syntax, title="Workflow Preview"))
        console.print()
    else:
        click.echo("\n--- Workflow Preview ---")
        click.echo(yaml_content)
        click.echo("--- End Preview ---\n")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py::TestPreviewYaml -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): add YAML preview with Rich syntax highlighting"
```

---

### Task 9: Wire everything together — `_custom_interactive_wizard`

**Files:**
- Modify: `src/binex/cli/start.py:426-489` (replace custom template path in wizard flow)
- Test: `tests/unit/test_custom_wizard.py`

**Step 1: Write the failing tests**

```python
class TestCustomWizardE2E:
    """End-to-end tests for the full custom interactive wizard."""

    def test_dsl_mode_full_flow(self, tmp_path, monkeypatch):
        """DSL mode → configure nodes → preview → save."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        # Template=5 (custom), mode=dsl, topology="A -> B",
        # --- node A config ---
        # type=1 (LLM), provider=1 (ollama), model=default, prompt=1 (first bundled),
        # back_edge=n, advanced=n,
        # --- node B config ---
        # type=1 (LLM), provider=1 (ollama), model=default, prompt=1,
        # back_edge=n, advanced=n,
        # --- finalize ---
        # save=y, project_name=e2e-dsl, run=n
        result = runner.invoke(
            start_cmd,
            input=(
                "5\n1\nA -> B\n"        # custom, DSL mode, topology
                "1\n1\n\n1\nn\nn\n"     # node A: LLM, ollama, default, prompt 1, no BE, no adv
                "1\n1\n\n1\nn\nn\n"     # node B: same
                "y\ne2e-dsl\nn\n"       # save, name, don't run
            ),
        )
        assert result.exit_code == 0
        proj = tmp_path / "e2e-dsl"
        assert (proj / "workflow.yaml").exists()
        data = yaml.safe_load((proj / "workflow.yaml").read_text())
        assert set(data["nodes"].keys()) == {"A", "B"}
        assert data["nodes"]["A"]["agent"].startswith("llm://")
        assert data["nodes"]["B"]["depends_on"] == ["A"]

    def test_step_mode_with_back_edge(self, tmp_path, monkeypatch):
        """Step mode → human review with back-edge → save."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            start_cmd,
            input=(
                "5\n2\n"                          # custom, step mode
                "generate\nreview\ndone\n"        # topology: generate -> review
                "1\n1\n\n1\nn\nn\n"               # node generate: LLM
                "2\ny\n1\n3\nn\n"                 # node review: human, back-edge to generate
                "y\nbe-proj\nn\n"                 # save, name, don't run
            ),
        )
        assert result.exit_code == 0
        data = yaml.safe_load((tmp_path / "be-proj" / "workflow.yaml").read_text())
        assert data["nodes"]["review"]["agent"] == "human://review"
        assert data["nodes"]["review"]["back_edge"]["target"] == "generate"

    def test_decline_save_returns_to_config(self, tmp_path, monkeypatch):
        """Declining save with option 1 returns to node config."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            start_cmd,
            input=(
                "5\n1\nA -> B\n"            # custom, DSL, topology
                "1\n1\n\n1\nn\nn\n"         # node A
                "1\n1\n\n1\nn\nn\n"         # node B
                "n\n2\n"                    # decline save, cancel
            ),
        )
        # Should exit cleanly (cancel)
        assert result.exit_code == 0

    def test_generated_yaml_loadable(self, tmp_path, monkeypatch):
        """Generated YAML should pass load_workflow validation."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            start_cmd,
            input=(
                "5\n1\nplanner -> writer\n"
                "1\n1\n\n1\nn\nn\n"
                "1\n1\n\n1\nn\nn\n"
                "y\nvalid-proj\nn\n"
            ),
        )
        assert result.exit_code == 0
        from binex.workflow_spec.loader import load_workflow
        from binex.workflow_spec.validator import validate_workflow

        spec = load_workflow(str(tmp_path / "valid-proj" / "workflow.yaml"))
        errors = validate_workflow(spec)
        assert errors == []
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_custom_wizard.py::TestCustomWizardE2E -v`
Expected: FAIL

**Step 3: Implement `_custom_interactive_wizard`**

Replace `_step_custom_template` call in the wizard flow. The function coordinates all phases:

```python
def _custom_interactive_wizard() -> tuple[str, str, set[str]]:
    """Full interactive custom workflow builder.

    Returns (yaml_content, project_default_name, needed_prompt_files).
    Replaces _step_custom_template in the wizard flow.
    """
    # Phase 1: Topology
    if has_rich():
        from binex.cli.ui import get_console
        console = get_console(stderr=True)
        console.print()
        console.print("  [bold]1)[/bold] [cyan]DSL[/cyan] — write topology as arrows")
        console.print("  [bold]2)[/bold] [cyan]Step-by-step[/cyan] — build nodes one at a time")
        console.print()
    else:
        click.echo()
        click.echo("  1) DSL — write topology as arrows (e.g. A -> B, C -> D)")
        click.echo("  2) Step-by-step — build nodes one at a time")
        click.echo()

    mode = click.prompt("Choose mode", type=click.Choice(["1", "2"]), default="1")

    if mode == "1":
        dsl = _get_dsl_input()
    else:
        dsl = _step_mode_topology()

    _print_confirm("Custom workflow")
    _print_dsl_preview(dsl)

    # Parse DSL to get node names and dependencies
    parsed = parse_dsl([dsl])

    while True:
        # Phase 2: Configure each node
        nodes_config = {}
        for node_id in parsed.nodes:
            deps = parsed.depends_on.get(node_id, [])
            config = _configure_node(node_id=node_id, dependencies=deps)
            nodes_config[node_id] = config

        # Phase 3: Preview and confirm
        yaml_content, needed_prompts = build_custom_workflow(
            name="custom-workflow", nodes_config=nodes_config,
        )
        _preview_yaml(yaml_content)

        save = click.prompt("Save workflow?", type=click.Choice(["y", "n"]), default="y")
        if save.lower() == "y":
            return yaml_content, "my-project", needed_prompts

        click.echo("  1) Return to node configuration")
        click.echo("  2) Cancel")
        action = click.prompt("Choose", type=click.Choice(["1", "2"]))
        if action == "2":
            click.echo("Cancelled.")
            sys.exit(0)
        # Loop back to Phase 2


def _get_dsl_input() -> str:
    """Get DSL topology string (with help text and pattern list)."""
    # ... (existing DSL help panel code from _step_custom_dsl) ...
    dsl_input = click.prompt("Pick a pattern name OR write your own topology")
    if dsl_input in PATTERNS:
        return PATTERNS[dsl_input]
    try:
        parse_dsl([dsl_input])
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    return dsl_input
```

Then update `_step_choose_template` to call `_custom_interactive_wizard` for custom choice, and update `_step_generate_project` to accept pre-built YAML + needed_prompts instead of calling `build_start_workflow`.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_custom_wizard.py -v`
Expected: ALL PASS

Also verify no regressions:
Run: `pytest tests/unit/test_cli_start.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/binex/cli/start.py tests/unit/test_custom_wizard.py
git commit -m "feat(start): wire up custom interactive wizard with 3-phase flow"
```

---

### Task 10: Regression test and lint

**Files:**
- No new files

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS (1436+ tests)

**Step 2: Run linter**

Run: `ruff check src/`
Expected: All checks passed!

**Step 3: Fix any issues found**

If any tests fail or lint errors appear, fix them.

**Step 4: Final commit if fixes needed**

```bash
git add -u
git commit -m "fix(start): address lint and test issues from custom wizard"
```
