# Tasks: Binex Runtime

**Input**: Design documents from `/specs/001-binex-runtime/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in spec. Test tasks omitted.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, packaging, and tooling

- [x] T001 Create project directory structure per plan.md (src/binex/, tests/unit/, tests/integration/, examples/, docker/)
- [x] T002 Initialize Python project with pyproject.toml (hatchling build backend, Python 3.11+, all dependencies: a2a-sdk, litellm, fastapi, uvicorn, httpx, pydantic 2.0+, pyyaml, click, aiosqlite; dev deps: pytest, pytest-asyncio, ruff, mypy)
- [x] T003 Initialize virtual environment with uv and install all dependencies (uv venv && uv pip install -e ".[dev]")
- [x] T004 [P] Configure ruff and mypy in pyproject.toml
- [x] T005 [P] Create src/binex/__init__.py with package version and public API exports
- [x] T006 [P] Create tests/conftest.py with shared fixtures (in-memory stores, sample workflow specs)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Domain models and storage layer that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Domain Models (zero internal dependencies)

- [x] T007 [P] Implement Artifact, ArtifactRef, Lineage models in src/binex/models/artifact.py (Pydantic 2.0+ BaseModel with id, run_id, type, content, status, lineage, created_at)
- [x] T008 [P] Implement TaskNode, TaskStatus enum, RetryPolicy models in src/binex/models/task.py (TaskStatus: requested/accepted/running/completed/failed/cancelled/timed_out with valid transitions)
- [x] T009 [P] Implement WorkflowSpec, NodeSpec, DefaultsSpec models in src/binex/models/workflow.py (Pydantic models matching workflow-spec.md contract schema)
- [x] T010 [P] Implement ExecutionRecord, RunSummary models in src/binex/models/execution.py (RunSummary includes forked_from/forked_at_step for replay)
- [x] T011 [P] Implement AgentInfo, AgentHealth enum models in src/binex/models/agent.py (AgentHealth: alive/slow/degraded/down)
- [x] T012 [P] Create src/binex/models/__init__.py re-exporting all public models

### Settings

- [x] T013 Implement application settings in src/binex/settings.py (store paths, default timeouts, registry URL, configurable via env vars)

### Store Protocols

- [x] T014 [P] Define ArtifactStore protocol in src/binex/stores/artifact_store.py (methods: store, get, list_by_run, get_lineage)
- [x] T015 [P] Define ExecutionStore protocol in src/binex/stores/execution_store.py (methods: record, get_run, get_step, list_runs, create_run, update_run)

### Store Backends

- [x] T016 [P] Implement InMemoryArtifactStore and InMemoryExecutionStore in src/binex/stores/backends/memory.py (for tests)
- [x] T017 [P] Implement FilesystemArtifactStore in src/binex/stores/backends/filesystem.py (store artifacts as JSON in .binex/artifacts/{run_id}/{artifact_id}.json)
- [x] T018 Implement SqliteExecutionStore in src/binex/stores/backends/sqlite.py (aiosqlite, tables: runs, execution_records, artifacts_meta per data-model.md)
- [x] T019 Create src/binex/stores/__init__.py and src/binex/stores/backends/__init__.py with factory functions for default store creation

**Checkpoint**: Foundation ready — all models defined, stores operational. User story implementation can begin.

---

## Phase 3: User Story 1 — Run a Multi-Agent Workflow (Priority: P1) MVP

**Goal**: Developer defines a YAML workflow, runs `binex run workflow.yaml`, Binex parses the DAG, schedules tasks, dispatches to agents, collects artifacts, returns result.

**Independent Test**: Run `binex run workflow.yaml` with a 2-agent workflow using LocalPythonAdapter, verify artifacts flow and final output is produced.

### Workflow Parsing

- [x] T020 [P] [US1] Implement workflow YAML/JSON loader in src/binex/workflow_spec/loader.py (parse YAML/JSON into WorkflowSpec, resolve variable interpolation ${node.output} and ${user.key})
- [x] T021 [P] [US1] Implement workflow structural validator in src/binex/workflow_spec/validator.py (cycle detection, missing depends_on refs, valid interpolation targets, at least one entry node)

### DAG Engine

- [x] T022 [P] [US1] Implement DAG construction and cycle detection in src/binex/graph/dag.py (build adjacency list from WorkflowSpec, topological sort, detect cycles with clear error messages)
- [x] T023 [US1] Implement scheduler with ready-node tracking in src/binex/graph/scheduler.py (track completed nodes, return ready nodes whose dependencies are all met, support parallel node dispatch)

### Agent Adapters

- [x] T024 [P] [US1] Define AgentAdapter protocol in src/binex/adapters/base.py (methods: execute, cancel, health per agent-adapter.md contract)
- [x] T025 [P] [US1] Implement LocalPythonAdapter in src/binex/adapters/local.py (execute agent as in-process Python callable, no network)
- [x] T026 [P] [US1] Implement LLMAdapter in src/binex/adapters/llm.py (direct LLM calls via litellm, prompt template from task spec)
- [x] T027 [P] [US1] Implement A2AAgentAdapter in src/binex/adapters/a2a.py (translate Binex artifacts to/from A2A message format via a2a-sdk, httpx for transport)

### Runtime Core

- [x] T028 [US1] Implement task lifecycle state machine in src/binex/runtime/lifecycle.py (enforce valid TaskStatus transitions per data-model.md, raise on invalid transition)
- [x] T029 [US1] Implement task dispatcher in src/binex/runtime/dispatcher.py (resolve adapter for task node, call adapter.execute with input artifacts, handle retries per RetryPolicy with backoff, enforce deadline_ms with asyncio timeout)
- [x] T030 [US1] Implement orchestrator in src/binex/runtime/orchestrator.py (load workflow -> build DAG -> create run -> schedule ready nodes -> dispatch in parallel via asyncio -> collect artifacts -> persist execution records -> return RunSummary)

### CLI

- [x] T031 [US1] Create CLI entry point with Click in src/binex/cli/main.py (top-level group `binex`, register all subcommands)
- [x] T032 [US1] Implement `binex run` command in src/binex/cli/run.py (accept workflow-file and --var options, invoke orchestrator, stream progress, output run ID and summary per cli.md contract)

### Example Workflows

- [x] T033 [P] [US1] Create simple 2-node example workflow in examples/simple.yaml (single producer -> consumer with LocalPythonAdapter)
- [x] T034 [P] [US1] Create research pipeline 5-node example workflow in examples/research.yaml (planner -> 2 researchers -> validator -> summarizer per workflow-spec.md contract example)

**Checkpoint**: `binex run examples/simple.yaml` works end-to-end with local adapters. Core DAG execution, artifact flow, retry, and deadline enforcement operational.

---

## Phase 4: User Story 2 — Trace and Inspect a Pipeline Run (Priority: P1)

**Goal**: After a run, developer inspects execution trace, per-step details, DAG visualization, and artifact lineage chain.

**Independent Test**: Run a pipeline, then use `binex trace <run_id>` for timeline, `binex trace graph <run_id>` for DAG viz, `binex artifacts lineage <artifact_id>` for provenance.

### Trace Engine

- [ ] T035 [P] [US2] Implement timeline trace generation in src/binex/trace/tracer.py (load ExecutionRecords for a run, format as human-readable timeline with agent, status, latency, artifact refs; support --json output)
- [ ] T036 [P] [US2] Implement artifact lineage traversal in src/binex/trace/lineage.py (given an artifact ID, walk derived_from chain recursively, build provenance tree with produced_by info)

### CLI

- [ ] T037 [US2] Implement `binex trace` command in src/binex/cli/trace.py (subcommands: default timeline, `graph` for ASCII DAG viz, `node` for single step detail per cli.md contract)
- [ ] T038 [US2] Implement `binex artifacts` command in src/binex/cli/artifacts.py (subcommands: list, show, lineage per cli.md contract; lineage renders tree view)

**Checkpoint**: Full trace and inspection workflow operational. `binex trace <run_id>` shows timeline, `binex artifacts lineage <id>` shows provenance chain.

---

## Phase 5: User Story 3 — Replay from a Specific Step (Priority: P2)

**Goal**: Developer replays a run from a specific step or with agent swaps. Replay creates a new immutable run reusing cached upstream artifacts.

**Independent Test**: Run a pipeline, then `binex replay <run_id> --from <step>` to re-execute from mid-pipeline, verify upstream artifacts are reused.

**Dependencies**: Requires US1 (orchestrator) and US2 (trace/execution records)

### Replay Engine

- [ ] T039 [US3] Implement replay logic in src/binex/runtime/replay.py (create new run from existing run, mark steps before --from as cached with linked artifacts, re-execute from --from step onward, support --agent node=agent swap per research.md R-009 immutable strategy)

### Diff Engine

- [ ] T040 [US3] Implement run diff comparison in src/binex/trace/diff.py (compare two runs step-by-step: artifact differences, execution metadata differences, status changes; support --json output)

### CLI

- [ ] T041 [US3] Implement `binex replay` command in src/binex/cli/replay.py (accept run-id, --from step, --agent node=agent per cli.md contract; output new run ID and cached/re-executed status per step)
- [ ] T042 [US3] Implement `binex diff` command in src/binex/cli/diff.py (accept two run IDs, display side-by-side comparison per cli.md contract)

**Checkpoint**: Replay and diff fully operational. `binex replay` creates new run with cached artifacts, `binex diff` compares runs.

---

## Phase 6: User Story 4 — Register and Discover Agents (Priority: P2)

**Goal**: Developer registers agents in local registry, registry crawls agent cards, indexes capabilities, tracks health, supports search.

**Independent Test**: Start registry, register agent endpoint, verify agent card is crawled/indexed, search by capability.

### Registry Service

- [ ] T043 [P] [US4] Implement FastAPI app with REST endpoints in src/binex/registry/app.py (POST/GET/DELETE /agents, GET /agents/search, GET /health per agent-adapter.md contract)
- [ ] T044 [P] [US4] Implement agent discovery/crawling in src/binex/registry/discovery.py (fetch A2A agent card from endpoint, parse capabilities, periodic refresh)
- [ ] T045 [US4] Implement capability index and search in src/binex/registry/index.py (index agent capabilities, search by capability with ranking by health/latency)
- [ ] T046 [US4] Implement health checker in src/binex/registry/health.py (periodic health checks, transition health status: alive -> slow -> degraded -> down based on consecutive failures and latency thresholds)
- [ ] T047 [US4] Create registry entry point in src/binex/registry/__main__.py (uvicorn launch with configurable host/port)

**Checkpoint**: Registry service runs standalone, agents can be registered, discovered, and searched by capability.

---

## Phase 7: User Story 5 — Local Development Environment (Priority: P2)

**Goal**: Developer runs `binex dev` to bootstrap complete local stack with Docker Compose (Ollama, reference agents, registry).

**Independent Test**: Run `binex dev`, verify all services start, run `binex doctor` for health check, run research pipeline example.

### Reference Agents

- [ ] T048 [P] [US5] Implement shared LLM config and client in src/binex/agents/common/llm_config.py and src/binex/agents/common/llm_client.py (LiteLLM wrapper with Ollama/cloud provider support)
- [ ] T049 [P] [US5] Implement planner reference agent in src/binex/agents/planner/ (A2A-compatible agent that decomposes research query into subtasks)
- [ ] T050 [P] [US5] Implement researcher reference agent in src/binex/agents/researcher/ (A2A-compatible agent that searches sources)
- [ ] T051 [P] [US5] Implement validator reference agent in src/binex/agents/validator/ (A2A-compatible agent that deduplicates and validates results)
- [ ] T052 [P] [US5] Implement summarizer reference agent in src/binex/agents/summarizer/ (A2A-compatible agent that produces structured report)

### Docker Setup

- [ ] T053 [P] [US5] Create Dockerfile in docker/Dockerfile (multi-stage: build binex package, run reference agents)
- [ ] T054 [US5] Create Docker Compose config in docker/docker-compose.yml (services: ollama, litellm-proxy, 4 reference agents, registry)

### CLI

- [ ] T055 [US5] Implement `binex dev` command in src/binex/cli/dev.py (start Docker Compose stack, wait for health, support --detach per cli.md contract)
- [ ] T056 [US5] Implement `binex doctor` command in src/binex/cli/doctor.py (check Docker, Ollama, agents reachability, registry status, store backends per cli.md contract)

**Checkpoint**: `binex dev` starts full local stack, `binex doctor` reports healthy, `binex run examples/research.yaml` completes with local models.

---

## Phase 8: User Story 6 — Validate and Scaffold Workflows (Priority: P3)

**Goal**: Developer validates workflow YAML before running (catches cycles, missing refs) and scaffolds new agent projects.

**Independent Test**: Run `binex validate workflow.yaml` on valid and invalid files, verify error/success messages.

- [ ] T057 [US6] Implement `binex validate` command in src/binex/cli/validate.py (load workflow, run validator, report errors or success summary with node/edge/agent counts per cli.md contract)
- [ ] T058 [US6] Implement `binex scaffold` command in src/binex/cli/scaffold.py (generate template agent project with A2A server setup, agent card, basic handler per cli.md contract)

**Checkpoint**: `binex validate` catches structural errors, `binex scaffold agent` generates working template.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, documentation, cleanup

- [ ] T059 [P] Implement `binex cancel` command in src/binex/cli/run.py (cancel a running workflow by run-id per cli.md contract)
- [ ] T060 [P] Add --json output flag support across all CLI commands that support it
- [ ] T061 Run quickstart.md validation (verify all commands from quickstart.md work end-to-end)
- [ ] T062 Code cleanup: ensure zero circular dependencies per plan.md constraint (models -> stores -> adapters/graph -> trace -> runtime -> cli)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — core execution pipeline
- **US2 (Phase 4)**: Depends on Phase 2; benefits from US1 for end-to-end testing
- **US3 (Phase 5)**: Depends on US1 and US2 (needs orchestrator + execution records)
- **US4 (Phase 6)**: Depends on Phase 2 only — independent of US1-US3
- **US5 (Phase 7)**: Depends on US1 (needs working runtime) and US4 (needs registry)
- **US6 (Phase 8)**: Depends on Phase 2 only (reuses workflow_spec/validator from US1 but can use it once available)
- **Polish (Phase 9)**: Depends on all user stories

### User Story Dependencies

```
Phase 1 (Setup)
    |
Phase 2 (Foundational)
    |
    +---> US1 (P1: Run Workflow) ----+---> US3 (P2: Replay/Diff)
    |                                |
    +---> US2 (P1: Trace/Inspect) ---+
    |
    +---> US4 (P2: Registry) --------+---> US5 (P2: Local Dev)
    |                                |
    +---> US6 (P3: Validate/Scaffold)     (also needs US1)
```

### Within Each User Story

- Models before services
- Protocols before implementations
- Services before CLI commands
- Core logic before integration

### Parallel Opportunities

**Phase 2**: T007-T012 (all models) can run in parallel; T014-T015 (store protocols) in parallel; T016-T017 (store backends) in parallel

**US1 (Phase 3)**: T020-T021 (workflow parsing) parallel with T022 (DAG) parallel with T024-T027 (adapters); T033-T034 (examples) parallel with CLI work

**US4 (Phase 6)**: T043-T044 (app + discovery) in parallel

**US5 (Phase 7)**: T048-T052 (all reference agents) in parallel; T053 (Dockerfile) parallel with agents

---

## Parallel Example: User Story 1

```bash
# Wave 1 — all independent modules in parallel:
Task T020: "Implement workflow loader in src/binex/workflow_spec/loader.py"
Task T021: "Implement workflow validator in src/binex/workflow_spec/validator.py"
Task T022: "Implement DAG construction in src/binex/graph/dag.py"
Task T024: "Define AgentAdapter protocol in src/binex/adapters/base.py"
Task T025: "Implement LocalPythonAdapter in src/binex/adapters/local.py"
Task T026: "Implement LLMAdapter in src/binex/adapters/llm.py"
Task T027: "Implement A2AAgentAdapter in src/binex/adapters/a2a.py"

# Wave 2 — depends on Wave 1:
Task T023: "Implement scheduler in src/binex/graph/scheduler.py"
Task T028: "Implement lifecycle state machine in src/binex/runtime/lifecycle.py"
Task T029: "Implement dispatcher in src/binex/runtime/dispatcher.py"

# Wave 3 — depends on Wave 2:
Task T030: "Implement orchestrator in src/binex/runtime/orchestrator.py"

# Wave 4 — depends on Wave 3:
Task T031: "Create CLI entry point in src/binex/cli/main.py"
Task T032: "Implement binex run command in src/binex/cli/run.py"
Task T033: "Create simple.yaml example"
Task T034: "Create research.yaml example"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (models + stores)
3. Complete Phase 3: User Story 1 (DAG execution + CLI run)
4. **STOP and VALIDATE**: `binex run examples/simple.yaml` works end-to-end
5. Demo core value proposition

### Incremental Delivery

1. Setup + Foundational -> Foundation ready
2. Add US1 (Run Workflow) -> Test independently -> MVP!
3. Add US2 (Trace/Inspect) -> Debuggability layer
4. Add US3 (Replay/Diff) -> Iterative development support
5. Add US4 (Registry) -> Agent discovery
6. Add US5 (Local Dev) -> Zero-config setup
7. Add US6 (Validate/Scaffold) -> Developer experience polish
8. Each story adds value without breaking previous stories

---

## Summary

- **Total tasks**: 62
- **Phase 1 (Setup)**: 6 tasks
- **Phase 2 (Foundational)**: 13 tasks
- **US1 (Run Workflow)**: 15 tasks
- **US2 (Trace/Inspect)**: 4 tasks
- **US3 (Replay/Diff)**: 4 tasks
- **US4 (Registry)**: 5 tasks
- **US5 (Local Dev)**: 9 tasks
- **US6 (Validate/Scaffold)**: 2 tasks
- **Polish**: 4 tasks
- **Parallel opportunities**: 30 tasks marked [P]
- **Suggested MVP scope**: Phase 1 + Phase 2 + US1 (34 tasks)
