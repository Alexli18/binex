# Binex

> Debuggable runtime for AI agent pipelines

## What is Binex?

Binex orchestrates multi-agent workflows defined in YAML. It executes DAG-based pipelines, records every execution step, and provides tools to trace, replay, and diff runs for full debuggability.

## Quick Example

```yaml
# workflow.yaml
name: simple-pipeline
description: "Simple 2-node pipeline with local adapters"

nodes:
  producer:
    agent: "local://echo"
    system_prompt: produce
    inputs:
      data: "${user.input}"
    outputs: [result]

  consumer:
    agent: "local://echo"
    system_prompt: consume
    inputs:
      data: "${producer.result}"
    outputs: [final]
    depends_on: [producer]
```

```bash
binex run workflow.yaml --var input="hello world"
```

## Example Output

```
Run: a1b2c3d4
Status: completed

Timeline:
  producer  ██████████  completed  1.2s
  consumer  ██████████  completed  0.8s

Artifacts: 2 produced
```

## Architecture

```
┌─────────────────────────────────────────┐
│                  CLI                     │
├─────────────────────────────────────────┤
│               Runtime                    │
│         (Orchestrator + Dispatcher)      │
├──────────┬──────────┬───────────────────┤
│ Adapters │  Graph   │  Workflow Spec     │
│ (LLM,   │  (DAG    │  (YAML loader,     │
│  A2A,   │  builder,│   variable         │
│  Local) │  topo-   │   resolution)      │
│          │  sort)   │                    │
├──────────┴──────────┴───────────────────┤
│               Stores                     │
│    (SQLite executions + FS artifacts)    │
├─────────────────────────────────────────┤
│               Models                     │
│  (Workflow, Node, Artifact, Execution)   │
└─────────────────────────────────────────┘
```

## Features

- **DAG-based workflows** — define multi-agent pipelines in YAML with dependency tracking
- **Five agent types** — `local://`, `llm://`, `a2a://`, `human://input`, and `human://approve` adapters
- **Human-in-the-loop** — interactive approval gates and free-text input with conditional branching
- **Full execution tracing** — every node execution recorded with timing and status
- **Post-mortem debugging** — `binex debug` assembles a complete report from any run with filtering and JSON/rich output
- **Replay with agent swap** — re-run workflows substituting different agents
- **Run diffing** — compare two executions side-by-side
- **Artifact lineage** — track provenance of every artifact through the pipeline
- **Built-in dev environment** — Docker Compose stack with Ollama, LiteLLM, and agent registry
- **Strict validation** — validate workflow YAML before execution

## Quickstart

```bash
pip install -e .
binex run examples/simple.yaml --var input="hello"
binex debug <run-id>
binex trace <run-id>
binex artifacts list <run-id>

# Optional: colored debug output
pip install -e ".[rich]"
binex debug <run-id> --rich
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `binex run` | Execute a workflow from a YAML file |
| `binex cancel` | Cancel a running workflow |
| `binex debug` | Post-mortem inspection (`--json`, `--errors`, `--node`, `--rich`) |
| `binex trace` | View execution timeline, node details, or DAG graph |
| `binex replay` | Re-run a workflow with optional agent swaps |
| `binex diff` | Compare two workflow runs |
| `binex artifacts` | List, show, or trace lineage of artifacts |
| `binex dev` | Start local development environment |
| `binex doctor` | Check system health (Docker, services, stores) |
| `binex validate` | Validate workflow YAML structure |
| `binex scaffold` | Generate agent project scaffolding |

## Agent Adapters

| Prefix | Adapter | Description |
|--------|---------|-------------|
| `local://` | LocalPythonAdapter | In-process Python callable |
| `llm://` | LLMAdapter | LLM completion via LiteLLM (OpenAI, Ollama, etc.) |
| `a2a://` | A2AAgentAdapter | Remote agent via A2A protocol (`POST /execute`) |
| `human://input` | HumanInputAdapter | Terminal prompt for free-text input |
| `human://approve` | HumanApprovalAdapter | Interactive approval gate (y/n → conditional branching) |

## Documentation

Full documentation is available at the [docs site](docs/index.md):

- [Quickstart](docs/quickstart.md) — install and run your first workflow
- [Concepts](docs/concepts/agents.md) — agents, workflows, artifacts, execution, lineage
- [CLI Reference](docs/cli/run.md) — all commands with options and examples
- [Architecture](docs/architecture/overview.md) — runtime internals
- [Workflow Format](docs/workflows/format.md) — YAML schema reference

## Roadmap

- Web UI for execution visualization
- Plugin system for custom adapters
- Workflow versioning and migration
- Distributed execution across multiple runtimes
- OpenTelemetry integration for observability

## License

MIT
