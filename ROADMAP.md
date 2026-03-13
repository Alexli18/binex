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

## v0.4 — Observability & Persistence

- [ ] OpenTelemetry integration (traces, metrics, spans)
- [ ] Workflow versioning and migration
- [ ] Export runs to Parquet / CSV for analysis
- [ ] Webhook notifications on run completion / failure

## v1.0 — Production Ready

- [ ] Web UI for execution visualization and timeline
- [ ] Distributed execution across multiple runtimes
- [ ] Workflow templates marketplace
- [ ] Role-based access control for shared deployments
- [ ] Helm chart for Kubernetes deployment
