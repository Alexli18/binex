# Quickstart

Install Binex and run your first workflow in under 5 minutes.

## Prerequisites

- Python 3.11 or later
- pip (or any PEP 517 compatible installer)

## Install

```bash
git clone https://github.com/Alexli18/binex.git
cd binex
pip install -e ".[dev]"
```

Verify the installation:

```bash
binex --version
```

## Step 1: Run the Built-in Demo

The fastest way to confirm everything works is the `hello` command. It runs a 2-node demo workflow entirely in memory — no API keys or config files needed.

```bash
binex hello
```

Expected output:

```
Running built-in hello-world workflow...

  [1/2] greeter ...
  [greeter] -> result:
Hello from Binex!

  [2/2] responder ...
  [responder] -> result:
{"greeter": "Hello from Binex!"}

Run completed (2/2 nodes)
Run ID: <run-id>

Next steps:
  binex debug <run-id>               — inspect the run
  binex init                       — create your own project
  binex run examples/simple.yaml   — try a workflow file
```

The `greeter` node produces the text "Hello from Binex!", and the `responder` node receives it as input and echoes back a JSON summary.

## Step 2: Run a Workflow File

Binex ships with example workflows in the `examples/` directory. The simplest one is `examples/simple.yaml`:

```yaml
# examples/simple.yaml
name: simple-pipeline
description: "Simple 2-node pipeline with local adapters"

nodes:
  # First node: produces data from user input
  producer:
    agent: "local://echo"
    system_prompt: produce
    inputs:
      data: "${user.input}"       # resolved at load time from user variables
    outputs: [result]

  # Second node: consumes the producer's output
  consumer:
    agent: "local://echo"
    system_prompt: consume
    inputs:
      data: "${producer.result}"  # runtime artifact reference to producer's output
    outputs: [final]
    depends_on: [producer]

# Global defaults applied to all nodes
defaults:
  deadline_ms: 30000              # 30-second timeout per node
  retry_policy:
    max_retries: 1
    backoff: exponential
```

Key things to note:

- **`${user.input}`** is resolved at load time from the `--var` flag you pass on the command line.
- **`${producer.result}`** is resolved at runtime — Binex automatically wires the producer's output artifact into the consumer's input.
- **`depends_on: [producer]`** declares the execution order. Binex builds a DAG and runs independent nodes in parallel.

Run it:

```bash
binex run examples/simple.yaml --var input="hello world"
```

Expected output:

```
Run <run-id> completed (2/2 nodes)
Terminal output:
  consumer -> final: hello world
```

The run ID is printed so you can inspect it later. Copy it for the next step.

## Step 3: Debug the Run

Use the `debug` command with the run ID from the previous step:

```bash
binex debug <run-id>
```

Expected output:

```
=== Debug: <run-id> ===
Workflow: simple-pipeline
Status:   completed (2/2 completed)
Duration: 0.003s

-- producer [completed] ------
  Agent:  local://echo
  Output: art_producer (result)

-- consumer [completed] ------
  Agent:  local://echo
  Input:  art_producer <- producer
  Output: art_consumer (result)
```

The debug report shows every node's status, its agent, input artifact lineage, and outputs.

### Debug Options

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable JSON output |
| `--errors` | Show only failed or timed-out nodes |
| `--node <id>` | Focus on a single node |
| `--rich` | Colored, formatted output (requires `pip install binex[rich]`) |

## Step 4: Trace the Timeline

```bash
binex trace <run-id>
```

Expected output:

```
Run: <run-id>
Status: completed

Timeline:
  producer  ██████████  completed  0.001s
  consumer  ██████████  completed  0.001s
```

The trace view gives you a visual timeline of node execution, making it easy to spot bottlenecks in larger workflows.

## Step 5: Validate Before Running

You can check a workflow file for errors without executing it:

```bash
binex validate examples/simple.yaml
```

This catches issues like missing dependencies, circular references, and invalid node configurations before you spend time on a run.

## Creating Your Own Project

Use the interactive init wizard to scaffold a new project:

```bash
binex init
```

Or use the scaffold command to generate a workflow from a DSL string:

```bash
binex scaffold workflow "planner -> researcher1, researcher2 -> summarizer"
```

This generates a YAML workflow file with the specified DAG topology.

## Next Steps

- [Concepts: Workflows](concepts/workflows.md) — Understand the workflow model, variables, conditionals, and defaults
- [Concepts: Agents](concepts/agents.md) — Learn about agent types: `local://`, `llm://`, `a2a://`, `human://`
- [CLI Reference](cli/run.md) — Full documentation for all CLI commands and options
- [Multi-Provider LLM](multi-provider.md) — Mix OpenAI, Anthropic, Ollama, and more in a single workflow
- [Workflow Format](workflows/format.md) — Complete YAML schema reference
