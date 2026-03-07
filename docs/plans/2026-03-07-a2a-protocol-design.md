# A2A Protocol — Reference Implementation Design

**Date**: 2026-03-07
**Status**: Approved
**PRD**: PRD.md v0.3

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scope | Full PRD (all 8 roadmap steps) | Complete reference implementation |
| Repo structure | Monorepo, split after MVP | Simpler coordination, clear boundaries |
| Language | Python | AI/ML ecosystem, PRD recommends Python first |
| Transport | HTTP/REST (initial) | Simple, universal, easy to test |
| Audience | Agent developers + platform engineers | SDK for devs, runtime/router for ops |
| LLM backend | Ollama (default), Claude/OpenAI (optional) | Local-first, no API keys required |
| Demo scenario | Research pipeline | planner → researcher → validator → summarizer |
| Conformance | Levels 1-3 | Core + Collaboration + Network (no Enterprise yet) |
| Architecture | Layer-by-Layer | Clear boundaries, easy to split later |

## Architecture

### Monorepo Structure

```
a2a/
├── packages/
│   ├── a2a-spec/             # Protocol specification
│   │   ├── schemas/          # JSON Schema files
│   │   │   ├── envelope.json
│   │   │   ├── task.json
│   │   │   ├── artifact.json
│   │   │   ├── capability.json
│   │   │   ├── agent-descriptor.json
│   │   │   └── error.json
│   │   └── docs/             # RFC-style documentation
│   │
│   ├── a2a-sdk/              # Python SDK
│   │   ├── a2a_sdk/
│   │   │   ├── models/       # Pydantic models from spec
│   │   │   ├── transport/    # HTTP client/server
│   │   │   ├── validation/   # Schema validation
│   │   │   └── helpers/      # Trace, artifact helpers
│   │   └── pyproject.toml
│   │
│   ├── a2a-runtime/          # Agent server runtime
│   │   ├── a2a_runtime/
│   │   │   ├── dispatch/     # Intent → handler routing
│   │   │   ├── context/      # Execution context
│   │   │   ├── artifacts/    # Artifact store
│   │   │   └── server/       # Agent server + decorators
│   │   └── pyproject.toml
│   │
│   ├── a2a-registry/         # Registry service
│   │   ├── a2a_registry/
│   │   │   ├── api/          # REST endpoints
│   │   │   ├── store/        # Agent store, capability index
│   │   │   └── health/       # Heartbeat
│   │   └── pyproject.toml
│   │
│   ├── a2a-router/           # Router service
│   │   ├── a2a_router/
│   │   │   ├── matching/     # Capability matching
│   │   │   ├── forwarding/   # Task dispatch
│   │   │   ├── retry/        # Retry/fallback
│   │   │   └── trace/        # Trace collection
│   │   └── pyproject.toml
│   │
│   ├── a2a-agents/           # Example agents (LLM-powered)
│   │   ├── agents/
│   │   │   ├── planner/      # Coordinates task graph
│   │   │   ├── researcher/   # LLM-powered research
│   │   │   ├── validator/    # Result validation
│   │   │   └── summarizer/   # Final report generation
│   │   └── pyproject.toml
│   │
│   ├── a2a-demo/             # Demo stack
│   │   ├── docker-compose.yml
│   │   ├── cli/              # CLI entry point
│   │   └── viewer/           # Trace/artifact viewer
│   │
│   └── a2a-conformance/      # Conformance tests
│       ├── tests/
│       │   ├── level1/       # Core Compatible
│       │   ├── level2/       # Collaboration Compatible
│       │   └── level3/       # Network Compatible
│       └── pyproject.toml
│
├── pyproject.toml            # Root workspace config
└── docker-compose.yml        # Dev environment
```

### Key Technology Choices

- **Pydantic** for models (strict validation, auto-serialization)
- **FastAPI/ASGI** for HTTP transport (async-first)
- **SQLite/in-memory** for registry store (simple, no external dependencies)
- **LiteLLM** for LLM provider abstraction (Ollama/Claude/OpenAI via unified interface)
- **Docker Compose** for demo stack

## Data Flow — Research Pipeline

```
User Query: "Find research on WiFi CSI soil detection"
     │
     ▼
┌─────────────┐  task_request    ┌─────────────┐
│   CLI /     │ ──────────────── │   Planner   │
│   Web UI    │                  │   Agent     │
└─────────────┘                  └──────┬──────┘
                                        │ creates task_graph (DAG)
                                        │
                          ┌─────────────┼─────────────┐
                          ▼             │             ▼
                   ┌────────────┐       │      ┌────────────┐
                   │ Researcher │       │      │ Researcher │
                   │ Agent (1)  │       │      │ Agent (2)  │
                   └─────┬──────┘       │      └─────┬──────┘
                         │              │            │
                         │  artifact    │   artifact │
                         │  (results)   │   (results)│
                         ▼              │            ▼
                   ┌─────────────────────────────────┐
                   │        Validator Agent          │
                   │   (validates, deduplicates)     │
                   └──────────────┬──────────────────┘
                                  │ artifact (validated_results)
                                  ▼
                   ┌──────────────────────────────────┐
                   │        Summarizer Agent          │
                   │   (creates final report)         │
                   └──────────────┬───────────────────┘
                                  │ artifact (research_report)
                                  ▼
                          User gets report
```

### Execution Modes

**Direct Mode:** Planner knows agent URIs, sends task_request directly. Discovery via registry for initial lookup, then direct communication.

**Routed Mode:** Planner sends task_request to Router. Router does capability matching via registry, forwards task. Handles retry/fallback, collects traces.

## Component Responsibilities

### a2a-spec
- JSON Schema for all protocol entities (envelope, task, artifact, capability, agent descriptor, error)
- Versioned schemas (`v0.3/`)
- Machine-readable conformance level definitions

### a2a-sdk
- **Models**: Pydantic models matching JSON schemas — `MessageEnvelope`, `Task`, `Artifact`, `Capability`, `AgentDescriptor`, `ErrorResponse`
- **Transport**: `A2AClient` (HTTP client), `A2AServer` (ASGI app)
- **Validation**: Envelope validation, conformance level checking
- **Helpers**: `TraceContext` (auto span_id, trace_id propagation), `ArtifactBuilder` (creation with lineage)

### a2a-runtime
- **Server**: `@capability("research.search")` decorators for handler registration. Agent server with automatic envelope handling and dispatch
- **Dispatch**: Intent → handler routing. Local capability registry
- **Context**: `ExecutionContext` — access to inputs, constraints, artifact creation, progress reporting
- **Artifacts**: In-memory artifact store with lineage tracking

### a2a-registry
- REST API: `POST /agents` (register), `GET /agents` (list), `GET /agents/search?capability=...` (search), `GET /agents/{uri}` (descriptor)
- In-memory store (SQLite optional for persistence)
- Heartbeat endpoint for health checking
- Capability index for fast search

### a2a-router
- Gateway API: receives task_request, finds agent via registry, forwards
- Capability matching: agent selection by intent + constraints (latency, policy)
- Retry/fallback: on failure — retry or alternative agent
- Trace collector: span aggregation into unified trace

### a2a-agents (LLM-powered, Ollama default)
- **Planner**: Receives user query, creates task graph (DAG), coordinates execution
- **Researcher**: Receives research intent, uses LLM for search query generation and analysis
- **Validator**: Checks results for consistency, deduplicates
- **Summarizer**: Creates final report from validated results

Each agent = separate process/container, communication only via A2A protocol.

### a2a-conformance
- Level 1 tests: envelope structure, task lifecycle (request → accept → progress → completed/failed), error format
- Level 2 tests: handoff flow, capability query/response, artifact creation/reference
- Level 3 tests: agent URI format, registry registration/search, routing metadata

## Error Handling

- **Transport level**: Network errors → configurable auto-retry. HTTP status codes map to A2A error codes
- **Protocol level**: `INVALID_SCHEMA`, `UNAUTHORIZED`, `CAPABILITY_NOT_SUPPORTED` → returned as `task_failed` with error payload
- **Runtime level**: Handler exceptions → `task_failed`. Timeout → `TIMEOUT`. Rate limiting → `RATE_LIMITED`
- **Router level**: All agents failed → `CAPABILITY_NOT_SUPPORTED`. Partial failure → retry another agent. Trace preserved even on error
- **Task Graph level**: Node failure → DAG execution stops on dependent tasks. Planner gets partial results + error info, decides: retry / skip / abort

## Testing Strategy

- **Unit tests**: Each package tested in isolation. Models, validation, dispatch logic
- **Integration tests**: Two agents communicating via HTTP. Registry discovery flow. Router forwarding flow
- **E2E tests**: Full research pipeline (Direct Mode). Full research pipeline (Routed Mode). With mock LLM backend for determinism
- **Conformance tests**: Separate `a2a-conformance` package. Runs against any A2A-compatible agent. Checks Level 1/2/3 compliance

## Observability

- Structured logging (JSON format) in all components
- OpenTelemetry-compatible tracing via `trace_id`/`span_id`
- Demo viewer shows execution graph, artifacts, timing
