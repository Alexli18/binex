# Binex

> Debuggable runtime for AI agent pipelines

Binex orchestrates multi-agent workflows defined in YAML. It executes DAG-based pipelines with any combination of LLM providers, records every step, and lets you trace, replay, debug, and diff runs — giving you full observability into your AI agent systems.

## Key Features

- **YAML-defined workflows** — Describe multi-agent pipelines as directed acyclic graphs with a simple, declarative format. No code required.
- **Multi-provider LLM support** — Mix OpenAI, Anthropic, Gemini, Ollama, Groq, Mistral, DeepSeek, Together, and OpenRouter in a single workflow via LiteLLM routing.
- **Full run observability** — Every node execution is recorded. Trace timelines, inspect artifacts, debug failures, and replay past runs.
- **Root-cause analysis** — Automatic failure diagnosis with cascade detection, latency anomaly flagging, and actionable recommendations.
- **Run bisection** — Find the exact divergence point between two runs with content similarity analysis.
- **Run diffing** — Compare two workflow runs side-by-side to understand what changed between executions.
- **Output schema validation** — Define JSON Schema for node outputs with automatic retry on validation failure.
- **Streaming LLM output** — Watch LLM tokens arrive in real-time with auto-detection for TTY terminals.
- **Agent-to-Agent (A2A) protocol** — Connect to remote A2A-compatible agent servers with built-in Gateway proxy for capability-based routing, automatic failover, and health monitoring.
- **Framework adapters** — Integrate LangChain chains, CrewAI crews, and AutoGen teams as workflow nodes via thin-wrapper adapters. Install only what you need with optional extras.
- **Plugin system** — Extend Binex with custom adapters using Python entry points or inline `adapter_class` configuration.
- **OpenTelemetry tracing** — Optional run-level and node-level spans for external collectors (Jaeger, Tempo), with zero overhead when disabled.
- **Workflow versioning** — Schema versioning with migration framework, plus workflow snapshots stored in SQLite for run reproducibility.
- **Export & webhooks** — Export run data to CSV/JSON, webhook notifications on run lifecycle events.
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
| [CLI Reference](cli/run.md) | All commands: `hello`, `init`, `run`, `debug`, `trace`, `replay`, `diff`, `artifacts`, `dev`, `doctor`, `validate`, `scaffold`, `cancel`, `start`, `explore`, `diagnose`, `bisect`, `gateway`, `plugins`, `export`, `workflow` |
| [Concepts](concepts/agents.md) | Core concepts: agents, workflows, artifacts, execution model, lineage tracking |
| [Architecture](architecture/overview.md) | Runtime internals: orchestrator, stores, adapters, scheduler, DAG engine |
| [Workflow Format](workflows/format.md) | YAML schema reference with node specs, variables, conditionals, and defaults |
| [Multi-Provider LLM](multi-provider.md) | Using multiple LLM providers in a single workflow |
| [Contributing](contributing/development.md) | Development setup, testing guide, and code style |

## Links

- [GitHub Repository](https://github.com/Alexli18/binex)
- [Documentation Site](https://alexli18.github.io/binex/)
- [Issue Tracker](https://github.com/Alexli18/binex/issues)
- [PyPI](https://pypi.org/project/binex/)

## License

Binex is released under the [MIT License](https://github.com/Alexli18/binex/blob/master/LICENSE).
