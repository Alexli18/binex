# Binex

> Debuggable runtime for AI agent pipelines

Binex orchestrates multi-agent workflows defined in YAML. It executes DAG-based pipelines, records every step, and lets you trace, replay, and diff runs.

## Get Started

```bash
pip install -e ".[dev]"
binex run examples/simple.yaml --var input="hello"
binex debug <run-id>
binex trace <run-id>
```

See the [Quickstart](quickstart.md) for a full walkthrough.

## Documentation

| Section | Description |
|---------|-------------|
| [CLI Reference](cli/run.md) | All commands: hello, init, run, debug, trace, replay, diff, artifacts, dev, doctor, validate, scaffold, cancel |
| [Concepts](concepts/agents.md) | Agents, workflows, artifacts, execution, lineage |
| [Architecture](architecture/overview.md) | Runtime internals, stores, adapters |
| [Workflows](workflows/format.md) | YAML format reference and examples |
| [Contributing](contributing/development.md) | Development setup and testing |
