# Changelog

## v0.4.0

Observability & Persistence release.

### Features

- **OpenTelemetry integration** — optional run-level and node-level tracing spans (`binex.run`, `binex.node.<id>`), zero overhead when disabled (no-op fallback)
- **Workflow schema versioning** — `version` field on workflows (default 1), migration framework for future schema changes
- **Workflow snapshots** — every `binex run` stores an immutable SHA256-deduplicated snapshot of the workflow definition in SQLite
- **`binex workflow version <file>`** — display the schema version of a workflow file
- **`binex workflow diff <run1> <run2>`** — compare workflow definitions used in two different runs (unified diff)
- **CSV/JSON export** — `binex export <run-id>` for run data export (`--format json`, `--last N`, `--include-artifacts`)
- **Webhook notifications** — run lifecycle events (completed, failed, budget exceeded) sent to configured webhook URLs

### Installation

```bash
pip install binex[telemetry]   # OpenTelemetry tracing (optional)
```

### Notes

- Existing workflows without a `version` field default to version 1 (backward compatible)
- `workflow_snapshots` SQLite table and `workflow_hash` column added via lazy migration
- OTEL tracing activates only when `opentelemetry` is installed AND `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_TRACES_EXPORTER` is set

## v0.3.0

Framework Adapters release.

### Features

- A2A Gateway — standalone proxy with routing, auth, fallback, health checking
- LangChain adapter — run LangChain chains as workflow nodes
- CrewAI adapter — integrate CrewAI crews via A2A protocol
- AutoGen adapter — bridge AutoGen agents into Binex pipelines
- Plugin system for custom adapters via entry points

## v0.2.0

Developer Experience release.

### Features

- `binex diagnose <run-id>` — automated root-cause analysis for failed runs
- `binex bisect <run-id>` — binary search for regression-introducing node
- Streaming output for long-running LLM nodes
- Improved `binex diff` with side-by-side artifact comparison
- Node output schema validation (`output_schema` in YAML)

## v0.1.0

First public release.

### Features

- DAG-based workflow runtime with topological scheduling
- Artifact lineage tracking across pipeline steps
- Replayable workflows with agent swap support
- Run diffing for side-by-side comparison
- CLI interface: run, debug, trace, replay, diff, artifacts, explore, scaffold, validate, doctor
- Agent adapters: LLM (via LiteLLM), local Python, A2A protocol, human-in-the-loop
- Human approval gates with conditional branching
- 9 LLM providers out of the box (OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Groq, Mistral, DeepSeek, Together)
- Rich colored output (optional)
- SQLite execution store + filesystem artifact store
- Interactive project initialization wizard
- DSL shorthand for workflow generation
- MkDocs documentation site
