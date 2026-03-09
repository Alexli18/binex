# binex scaffold

## Synopsis

```
binex scaffold agent [OPTIONS]
binex scaffold workflow [OPTIONS] [DSL...]
```

## Description

Generate template projects for Binex agents and workflows. The `scaffold` command has two subcommands:

- **`scaffold agent`** — creates a ready-to-run A2A agent project with a FastAPI server, agent handler, agent card, and dependency file.
- **`scaffold workflow`** — generates a workflow YAML from a DSL topology string or a predefined pattern.

---

## scaffold agent

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `--name` | `string` | `my-agent` | Agent name (used for class and directory) |
| `--dir` | `Path` | `./<name>` | Target directory (created if missing) |

### Generated Files

| File | Purpose |
|---|---|
| `__init__.py` | Python package marker (empty) |
| `agent.py` | Agent handler class with `handle()` method |
| `agent_card.json` | A2A agent card served at `/.well-known/agent.json` |
| `server.py` | FastAPI server with `/` and `/.well-known/agent.json` routes |
| `requirements.txt` | Dependencies: `a2a-sdk`, `fastapi`, `uvicorn` |

The agent name is converted to PascalCase for the class name. For example, `--name planner` produces class `PlannerAgent`, and `--name data-fetcher` produces `DataFetcherAgent`.

### Example

```bash
# Scaffold with defaults
binex scaffold agent

# Custom name and directory
binex scaffold agent --name planner --dir ./agents/planner
```

**Output:**

```
Agent 'planner' scaffolded at agents/planner
```

**Generated directory:**

```
planner/
  __init__.py
  agent.py          # PlannerAgent class with handle() method
  agent_card.json   # A2A card with echo skill
  server.py         # FastAPI server on port 8000
  requirements.txt  # a2a-sdk, fastapi, uvicorn
```

**Generated `agent.py` preview:**

```python
"""Agent handler for planner."""

from __future__ import annotations
from typing import Any


class PlannerAgent:
    """A simple echo agent that returns whatever it receives."""

    name = "planner"

    async def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        """Process an incoming message and return a response."""
        return {
            "agent": self.name,
            "echo": message,
        }
```

**Running the scaffolded agent:**

```bash
cd agents/planner
pip install -r requirements.txt
python server.py
# Server starts on http://localhost:8000
```

### Safety

The command refuses to overwrite an existing non-empty directory:

```
Error: directory 'agents/planner' already exists and is not empty.
```

---

## scaffold workflow

Generate a workflow YAML file from a DSL topology string or a predefined pattern.

### Options

| Option | Type | Default | Description |
|---|---|---|---|
| `DSL` | positional args | — | One or more DSL topology strings |
| `--name` | `string` | `pipeline.yaml` | Output filename |
| `--pattern` | `string` | — | Use a predefined pattern instead of DSL |
| `--list-patterns` | flag | — | Show all available patterns and exit |
| `--no-interactive` | flag | — | Use `local://echo` stubs (skip provider prompts) |
| `--env` | flag | — | Generate `.env.example` alongside the YAML |

### DSL Syntax

The DSL uses `->` for sequential flow and `,` for parallel branches:

| Syntax | Meaning |
|---|---|
| `A -> B` | A flows into B (sequential) |
| `A -> B, C` | A fans out to B and C (parallel) |
| `A, B -> C` | A and B fan in to C (join) |
| `A -> B, C -> D` | Diamond: A fans out to B and C, both feed into D |

Each layer (separated by `->`) can contain multiple comma-separated nodes. Every node in layer N connects to every node in layer N+1.

### Predefined Patterns

Use `--list-patterns` to see all available patterns:

```bash
binex scaffold workflow --list-patterns
```

```
Pattern                      DSL
------------------------------------------------------------
linear                       A -> B -> C
fan-out                      planner -> researcher1, researcher2, researcher3
fan-in                       source1, source2, source3 -> aggregator
fan-out-fan-in               planner -> r1, r2, r3 -> summarizer
diamond                      A -> B, C -> D
multi-stage                  A -> B, C -> D, E -> F
chain-with-review            draft -> review -> revise -> final
map-reduce                   split -> worker1, worker2, worker3 -> reduce
pipeline-with-validation     input -> process -> validate -> output
human-approval               draft -> approve -> publish
human-feedback               generate -> human-review -> revise -> output
conditional-routing          classifier -> premium_handler, standard_handler -> reporter
error-handling               setup -> risky -> cleanup
a2a-multi-agent              coordinator -> researcher -> reviewer
research                     planner -> researcher1, researcher2 -> validator -> summarizer
secure-pipeline              fetcher -> processor -> writer
multi-provider               planner -> researcher -> summarizer
```

### Examples

```bash
# Simple linear pipeline with echo stubs
binex scaffold workflow "A -> B -> C" --no-interactive

# Fan-out pattern using echo stubs
binex scaffold workflow "planner -> r1, r2, r3 -> summarizer" --no-interactive

# Use a predefined pattern
binex scaffold workflow --pattern research --no-interactive

# Custom filename and generate .env.example
binex scaffold workflow --pattern diamond --name my-workflow.yaml --env --no-interactive

# Interactive mode (prompts for provider/model per node)
binex scaffold workflow "draft -> review -> publish"
```

### Interactive Mode

Without `--no-interactive`, the command prompts for each node's LLM provider, model, and system prompt:

```
--- Node: planner ---
Providers:
  1. ollama (ollama/llama3.2)
  2. openai (gpt-4o)
  3. anthropic (claude-sonnet-4-20250514)
  4. gemini (gemini/gemini-2.0-flash)
  5. groq (groq/llama3-70b-8192)
  6. mistral (mistral/mistral-large-latest)
  7. deepseek (deepseek/deepseek-chat)
  8. together (together_ai/meta-llama/Llama-3-70b)
  9. openrouter (openrouter/google/gemini-2.5-flash)
Choose provider (1-9): 2
Model [gpt-4o]:
System prompt [Process input]: Create a detailed research plan

--- Node: researcher ---
Providers:
  1. ollama (ollama/llama3.2)
  ...
Choose provider (1-9) [Enter = same as previous: openai]:
Model [gpt-4o]:
System prompt [Process input]: Research the topic thoroughly
```

Human-in-the-loop nodes (names containing `approve`, `confirm`, `gate`, `input`, `feedback`, `edit`, `ask`, `human`, `review`) are auto-detected:

```
--- Node: approve ---
Detected human node. Use human://approve? [y]:
System prompt [Review and approve]:
```

### Generated Workflow Preview

Running `binex scaffold workflow "planner -> r1, r2 -> summarizer" --no-interactive`:

```yaml
name: pipeline
description: 'Auto-generated workflow: pipeline'
nodes:
  planner:
    agent: local://echo
    system_prompt: Process input
    inputs:
      query: ${user.query}
    outputs:
    - output
  r1:
    agent: local://echo
    system_prompt: Process input
    inputs:
      planner: ${planner.output}
    outputs:
    - output
    depends_on:
    - planner
  r2:
    agent: local://echo
    system_prompt: Process input
    inputs:
      planner: ${planner.output}
    outputs:
    - output
    depends_on:
    - planner
  summarizer:
    agent: local://echo
    system_prompt: Process input
    inputs:
      r1: ${r1.output}
      r2: ${r2.output}
    outputs:
    - output
    depends_on:
    - r1
    - r2
```

### Combining Scaffold with Run

A typical workflow: scaffold, validate, then execute:

```bash
# Generate a workflow from a pattern
binex scaffold workflow --pattern research --no-interactive --name research.yaml

# Validate the generated file
binex validate research.yaml

# Run it
binex run research.yaml --var query="Analyze trends in AI agents"
```

### Generating .env.example

The `--env` flag creates a `.env.example` with placeholders for all provider API keys:

```bash
binex scaffold workflow --pattern research --no-interactive --env
```

**Generated `.env.example`:**

```bash
# API keys for LLM providers
# Uncomment and fill in the ones you need

# OPENAI_API_KEY=your-key-here
# ANTHROPIC_API_KEY=your-key-here
# GEMINI_API_KEY=your-key-here
# GROQ_API_KEY=your-key-here
# MISTRAL_API_KEY=your-key-here
# DEEPSEEK_API_KEY=your-key-here
# TOGETHER_API_KEY=your-key-here
# OPENROUTER_API_KEY=your-key-here
```

## See Also

- [binex validate](validate.md) — validate workflows that reference your agent
- [binex run](run.md) — execute generated workflows
- [binex dev](dev.md) — run agents in the local development environment
