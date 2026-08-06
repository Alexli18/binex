# Roadmap

## v0.2 — Developer Experience ✅

- [x] `binex diagnose <run-id>` — automated root-cause analysis for failed runs
- [x] `binex bisect <run-id>` — binary search for the node that introduced a regression
- [x] Streaming output for long-running LLM nodes
- [x] Improved `binex diff` with side-by-side artifact comparison
- [x] Node output schema validation (`output_schema` in YAML) — fail fast on malformed data

## v0.3 — Framework Adapters ✅

- [x] A2A Gateway — standalone proxy with routing, auth, fallback, health checking
- [x] LangChain adapter — run LangChain chains as workflow nodes
- [x] CrewAI adapter — integrate CrewAI crews via A2A protocol
- [x] AutoGen adapter — bridge AutoGen agents into Binex pipelines
- [x] Plugin system for custom adapters

## v0.4 — Observability & Persistence ✅

- [x] OpenTelemetry integration (traces, metrics, spans)
- [x] Workflow versioning and migration
- [x] Export runs to CSV / JSON for analysis
- [x] Webhook notifications on run completion / failure / budget exceeded

## Active Track — Debugger & Regression Testing

- [x] Web UI — visual workflow editor and run dashboard
- [x] Built-in tools + MCP client (10 built-in tools, stdio/HTTP MCP servers)
- [x] Loop container nodes — iterative execution with exit conditions
- [x] CAO adapter — CLI Agent Orchestrator integration
- [~] `binex eval` — regression testing suites, baselines, verdicts, CI annotations (in progress)
- [~] `binex mcp serve` — MCP tool server for coding agents (Claude Code, Cursor) (in progress)
- [~] `binex import otel` — import OpenTelemetry traces from LangChain / LlamaIndex (in progress)

## Deferred

- [ ] Distributed execution across multiple runtimes
- [ ] Workflow templates marketplace
- [ ] Role-based access control for shared deployments
- [ ] Helm chart / Kubernetes deployment
