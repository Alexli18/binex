# Binex

> Debuggable runtime for AI agent pipelines

Binex orchestrates multi-agent workflows defined in YAML. It executes DAG-based pipelines with any combination of LLM providers, records every step, and lets you trace, replay, debug, and diff runs — giving you full observability into your AI agent systems.

## Key Features

- **YAML-defined workflows** — Describe multi-agent pipelines as directed acyclic graphs with a simple, declarative format. No code required.
- **Multi-provider LLM support** — Mix OpenAI, Anthropic, Gemini, Ollama, Groq, Mistral, DeepSeek, Together, and OpenRouter in a single workflow via LiteLLM routing.
- **Full run observability** — Every node execution is recorded. Trace timelines, inspect artifacts, debug failures, and replay past runs.
- **Run diffing** — Compare two workflow runs side-by-side to understand what changed between executions.
- **Agent-to-Agent (A2A) protocol** — Connect to remote A2A-compatible agent servers alongside local and LLM-backed agents.
- **Interactive CLI** — Project scaffolding, workflow validation, a built-in doctor command, and a start wizard to get you productive quickly.

## Install

```bash
pip install -e ".[dev]"
```

## Quick Demo

```bash
binex hello                    # run a built-in demo workflow
binex run examples/simple.yaml # run a sample pipeline
binex debug <run-id>           # inspect the completed run
```

See the [Quickstart](quickstart.md) for a full walkthrough.

## Documentation

| Section | Description |
|---------|-------------|
| [Quickstart](quickstart.md) | Install Binex and run your first workflow in under 5 minutes |
| [CLI Reference](cli/run.md) | All commands: `hello`, `init`, `run`, `debug`, `trace`, `replay`, `diff`, `artifacts`, `dev`, `doctor`, `validate`, `scaffold`, `cancel`, `start`, `explore` |
| [Concepts](concepts/agents.md) | Core concepts: agents, workflows, artifacts, execution model, lineage tracking |
| [Architecture](architecture/overview.md) | Runtime internals: orchestrator, stores, adapters, scheduler, DAG engine |
| [Workflow Format](workflows/format.md) | YAML schema reference with node specs, variables, conditionals, and defaults |
| [Multi-Provider LLM](multi-provider.md) | Using multiple LLM providers in a single workflow |
| [Contributing](contributing/development.md) | Development setup, testing guide, and code style |

## Links

- [GitHub Repository](https://github.com/Alexli18/binex)
- [Documentation Site](https://alexli18.github.io/binex/)
- [Issue Tracker](https://github.com/Alexli18/binex/issues)
- [PyPI](https://pypi.org/project/binex/) (coming soon)

## License

Binex is released under the [MIT License](https://github.com/Alexli18/binex/blob/master/LICENSE).
