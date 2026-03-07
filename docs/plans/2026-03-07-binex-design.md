# Binex Design Document

**Date**: 2026-03-07
**Status**: Approved
**Branch**: `001-a2a-protocol`

## Positioning

**Binex — debuggable runtime for A2A agents.**
**Binex runs, traces, and replays agent workflows.**

```
LLM agents → A2A protocol → Binex runtime → task graphs / workflows / coordination
```

Binex is an orchestration runtime, not a protocol. It builds on top of Google A2A SDK to provide DAG-based workflow execution, artifact lineage, and time-travel debugging — capabilities that the A2A ecosystem currently lacks.

Any A2A-compatible agent can participate in Binex pipelines: LangChain, AutoGen, CrewAI, custom agents.

### Three Killer Features

1. **Trace + Replay** — time-travel debugging for agent pipelines
2. **Artifact-first** — typed artifacts with lineage, not message chains
3. **Pluggable adapters** — any A2A / local / LLM agent can participate

---

## Section 1: Architecture

```
Binex

Core Libraries
 ├─ Task Graph Engine
 │   ├─ DAGExecutor
 │   ├─ Scheduler
 │   └─ ParallelExecutor
 │
 ├─ Execution Store
 │   ├─ record(run_id, task_id, agent, input,
 │   │         output, prompt, model, latency)
 │   ├─ get_run(run_id) → full execution chain
 │   ├─ get_step(run_id, task_id) → snapshot
 │   └─ backend: SQLite (default) / Postgres / DuckDB
 │
 ├─ Execution Trace
 │   ├─ trace(run_id) → human-readable timeline
 │   ├─ graph(run_id) → DAG visualization
 │   └─ lineage: artifact provenance chains
 │
 └─ Replay Engine
     ├─ replay(run_id, from_step) → resume pipeline
     ├─ replay(run_id, agent_swap={}) → A/B test
     └─ diff(run_a, run_b) → step-by-step comparison

Runtime
 ├─ Orchestrator (wires graph + scheduler + stores)
 ├─ Dispatcher (dispatches tasks via adapters)
 ├─ Lifecycle (task state machine)
 └─ Agent Communication Layer (A2A SDK)

Agent Adapters (pluggable backends)
 ├─ A2AAgentAdapter      (Google A2A SDK)
 ├─ LocalPythonAdapter   (in-process agents)
 └─ LLMAdapter           (direct LiteLLM calls)

Services
 ├─ Agent Registry
 │   ├─ register / crawl agent cards
 │   ├─ capability index + search
 │   ├─ health tracking (alive / slow / degraded / down)
 │   └─ capability-aware selection
 │       (capability, health, latency, cost)
 │
 └─ A2A Gateway (Phase 2)
     └─ proxy / routing / auth / fallback

Workflow Spec
 └─ YAML / JSON DAG definition

CLI
 ├─ binex run workflow.yaml
 ├─ binex dev              (local stack)
 ├─ binex trace <run_id>
 ├─ binex trace graph <run_id>
 ├─ binex trace node <run_id> <step>
 ├─ binex replay <run_id> --from <step>
 ├─ binex replay <run_id> --deterministic
 ├─ binex diff <run_a> <run_b>
 ├─ binex artifacts list <run_id>
 ├─ binex artifacts show <artifact_id>
 ├─ binex artifacts lineage <artifact_id>
 ├─ binex doctor
 ├─ binex validate workflow.yaml
 └─ binex scaffold agent

Reference Agents
 ├─ Planner / Researcher / Validator / Summarizer

Local Runtime
 ├─ Docker Compose + Ollama + LiteLLM

Dependencies
 ├─ Agent protocol: Google A2A SDK
 └─ LLM abstraction: LiteLLM
```

### Task Lifecycle State Machine

```
requested → accepted → running → completed
                              → failed
                              → cancelled
                              → timed_out

+ deadline per task
+ retry_policy per task
```

### Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Task Graph Engine | Library inside Planner agent | Planner is itself an A2A agent. Fully A2A-native. |
| Registry model | Pull-based (crawl Agent Cards) | Agents are passive. Registry actively collects from seed URLs. |
| Router | Separate A2A-agent proxy (Phase 2) | Two modes: Direct (Planner → Agent) and Routed (Planner → Gateway → Agent). |
| Artifact lineage | metadata in standard A2A Artifacts | `lineage.derived_from`, `lineage.produced_by` keys. Compatible with A2A. |
| MVP scope | Full pipeline in Direct Mode, no Router | Task Graph + Registry + Lineage + 4 agents + CLI + Docker Compose. |
| Project structure | Single Python package `binex` | No monorepo overhead. `pip install binex`. |
| Naming | `binex` | "Debuggable runtime for autonomous agents." |

### Dependency Isolation Rules

- `a2a-sdk` is used **only** inside `adapters/a2a.py`. Orchestration core must not depend on SDK internals.
- `trace` operates on stores and models, not on runtime internals. No circular deps.
- `models/` has zero internal dependencies. It is the foundation layer.

---

## Section 2: Data Flow

### 2.0 — Two Parallel Flows

Binex maintains two parallel data flows:

```
1. Artifact Flow
   typed business outputs flowing between task nodes
   task → artifact → next task (not message → message)

2. Execution Flow
   metadata about execution state, trace, timing, and replayability
   → enables replay, diff, and debug
```

### 2.1 — Main Pipeline Flow

```
User                Orchestrator       Scheduler          Dispatcher
  │                      │                 │                  │
  │── run workflow.yaml─→│                 │                  │
  │                      │── parse DAG ───→│                  │
  │                      │                 │── ready nodes ──→│
  │                      │                 │                  │
  │                      │                 │   For each node: │
  │                      │                 │                  │
  │                      │                 │   1. resolve     │
  │                      │                 │      adapter     │
  │                      │                 │                  │
  │                      │                 │   2. collect     │
  │                      │                 │      input       │
  │                      │                 │      artifacts   │
  │                      │                 │      from Store  │
  │                      │                 │                  │
  │                      │                 │   3. execute     │
  │                      │                 │      via adapter │
  │                      │                 │                  │
  │                      │                 │   4. receive     │
  │                      │                 │      output      │
  │                      │                 │      artifact    │
  │                      │                 │                  │
  │                      │                 │   5. persist     │
  │                      │                 │      artifact →  │
  │                      │                 │      Artifact    │
  │                      │                 │      Store       │
  │                      │                 │                  │
  │                      │                 │   6. persist     │
  │                      │                 │      execution   │
  │                      │                 │      record →    │
  │                      │                 │      Execution   │
  │                      │                 │      Store       │
  │                      │                 │                  │
  │                      │                 │   7. transition  │
  │                      │                 │      node status │
  │                      │                 │      → completed │
  │                      │                 │                  │
  │                      │                 │   8. unblock     │
  │                      │                 │      downstream  │
  │                      │                 │      nodes       │
  │                      │                 │                  │
  │                      │                 │── next ready ───→│
  │                      │                 │       ...        │
  │                      │                 │                  │
  │←── final artifact ──│←── DAG done ───│                  │
  │                      │                 │                  │
                    ┌─────────┐      ┌──────────┐
                    │Artifact │      │Execution │
                    │Store    │      │Store     │
                    └─────────┘      └──────────┘
```

### 2.2 — Artifact Flow (research pipeline example)

```
run_42: "Find research on WiFi CSI sensing"

Step 1: planner
  input:  UserQuery("Find research on WiFi CSI sensing")
  output: Artifact<execution_plan>
          ├─ subtasks: [researcher_1, researcher_2, validator, summarizer]
          ├─ edges: [r1→val, r2→val, val→sum]
          └─ per-subtask: agent hint, query, constraints

  Orchestrator materializes execution_plan into runtime DAG nodes.
  Planner thinks (what to do). Runtime executes (how to do it).

Step 2a: researcher_1                   Step 2b: researcher_2
  input:  Artifact<execution_plan>        input:  Artifact<execution_plan>
          + query: "arxiv WiFi CSI"               + query: "scholar CSI soil"
  output: Artifact<search_results>        output: Artifact<search_results>
          ├─ 8 papers                             ├─ 6 papers
          ├─ produced_by: researcher_1            ├─ produced_by: researcher_2
          └─ derived_from: [art_plan_01]          └─ derived_from: [art_plan_01]

         ↓ parallel ↓                             ↓ parallel ↓

Step 3: validator
  input:  Artifact<search_results> x 2   (from both researchers)
  output: Artifact<validated_results>
          ├─ 9 unique papers (deduplicated)
          ├─ produced_by: validator
          └─ derived_from: [art_research_01, art_research_02]

Step 4: summarizer
  input:  Artifact<validated_results>
  output: Artifact<summary_report>
          ├─ structured report
          ├─ produced_by: summarizer
          └─ derived_from: [art_validated_03]
```

### 2.3 — Runtime Stores

```
Artifact Store
  Stores typed outputs produced by task nodes.

  Operations:
    store(artifact) → ArtifactRef
    get(artifact_id) → Artifact
    list_by_run(run_id) → [Artifact]
    get_lineage(artifact_id) → LineageTree

  Backend: filesystem (default) / S3 / in-memory

Execution Store
  Stores node execution metadata for replay/debug.

  Operations:
    record(execution_record) → record_id
    get_run(run_id) → [ExecutionRecord]
    get_step(run_id, task_id) → ExecutionRecord | None
    list_runs() → [RunSummary]

  Backend: SQLite (default) / Postgres / DuckDB
```

### 2.4 — Execution Record Model

One record per node execution:

```json
{
  "run_id": "run_42",
  "task_id": "researcher_1",
  "parent_task_id": "planner",
  "agent_id": "researcher@local:9001",
  "status": "completed",
  "input_artifact_refs": ["art_plan_01"],
  "output_artifact_refs": ["art_research_01"],
  "prompt": "Search arxiv for papers on WiFi CSI...",
  "model": "ollama_chat/qwen2.5:7b",
  "tool_calls": [],
  "latency_ms": 4200,
  "timestamp": "2026-03-07T14:23:01Z",
  "trace_id": "trace_abc123",
  "error": null
}
```

### 2.5 — Replay Flow

**Rule: replay always creates a new run. Original run is immutable.**

```
binex replay run_42 --from validator

Load Execution Store (run_42):
  ├─ planner:       SKIP → reuse cached art_plan_01
  ├─ researcher_1:  SKIP → reuse cached art_research_01
  ├─ researcher_2:  SKIP → reuse cached art_research_02
  │
  │  Create new run_43:
  │  ├─ steps 1-2: linked to run_42 cached artifacts (not re-executed)
  │
  ├─ validator:     RE-EXECUTE
  │   input:  cached [art_research_01, art_research_02]
  │   output: NEW art_validated_05
  │
  └─ summarizer:    RE-EXECUTE
      input:  [art_validated_05]
      output: NEW art_summary_06

Result: run_43 (fork of run_42 from step validator)
```

### 2.6 — Agent Swap Flow

**Agent swap does not mutate the original run. It creates a new run with modified node-to-agent binding.**

```
binex replay run_42 --agent validator=strict_validator

Creates run_44:
  ├─ planner:       reuse cached artifacts from run_42
  ├─ researcher_1:  reuse cached artifacts from run_42
  ├─ researcher_2:  reuse cached artifacts from run_42
  ├─ validator:     RE-EXECUTE with strict_validator (not validator)
  │   same inputs, different agent
  └─ summarizer:    RE-EXECUTE
      new inputs from strict_validator
```

### 2.7 — Diff Flow (two levels)

```
binex diff run_42 run_44

=== Artifact Diff ===
+──────────────+────────────────────+────────────────────+
| step         | run_42             | run_44             |
+──────────────+────────────────────+────────────────────+
| planner      | = same (cached)    | = same (cached)    |
| researcher_1 | = same (cached)    | = same (cached)    |
| researcher_2 | = same (cached)    | = same (cached)    |
| validator    | 9 papers           | 7 papers     <DIFF |
| summarizer   | report v1          | report v2    <DIFF |
+──────────────+────────────────────+────────────────────+

=== Execution Diff ===
+──────────────+────────────────────+────────────────────+
| step         | run_42             | run_44             |
+──────────────+────────────────────+────────────────────+
| validator    | agent: validator   | agent: strict_val  |
|              | latency: 2100ms    | latency: 3800ms    |
|              | model: qwen2.5:7b  | model: qwen2.5:7b  |
| summarizer   | latency: 1800ms    | latency: 2200ms    |
+──────────────+────────────────────+────────────────────+
```

### 2.8 — Artifact Lineage Chain

```
binex artifacts lineage art_summary_06

art_summary_06 (summary_report)
  produced_by: summarizer
  derived_from: art_validated_05 (validated_results)
      produced_by: strict_validator
      derived_from:
        ├─ art_research_01 (search_results)
        │   produced_by: researcher_1
        │   derived_from: art_plan_01
        │       produced_by: planner
        │       derived_from: [user_query]
        └─ art_research_02 (search_results)
            produced_by: researcher_2
            derived_from: art_plan_01
```

### 2.9 — Failure & Timeout Flow

**Failure:**
```
If a node fails:
  1. status → failed
  2. error_code + error_message recorded in execution record
  3. partial output artifacts MAY be persisted (status: partial)
  4. downstream nodes remain blocked
  5. scheduler checks retry_policy:
     - retries_left > 0 → re-execute node
     - retries_left = 0 → mark node terminal
  6. if all downstream blocked and no retries:
     - run status → failed
     - run is fully replayable from failed node
```

**Timeout:**
```
If execution exceeds deadline:
  1. dispatcher cancels agent call
  2. partial artifacts MAY be persisted
  3. execution record: status → timed_out
  4. scheduler marks node terminal
  5. downstream policy decides:
     - strict: block all downstream → run fails
     - degraded: continue with available artifacts
```

**Cancellation:**
```
binex cancel run_42
  1. scheduler stops dispatching new nodes
  2. running nodes receive cancel signal via adapter
  3. execution records: status → cancelled
  4. run is replayable from any cancelled node
```

---

## Section 3: Project Structure

### 3.1 — Package Layout

```
binex/
├── pyproject.toml                      # single package, hatchling backend
├── uv.lock
├── README.md
│
├── src/binex/
│   ├── __init__.py                     # version, top-level exports
│   ├── settings.py                     # global config (env vars, paths, defaults)
│   │
│   ├── models/                         # shared domain models (zero internal deps)
│   │   ├── artifact.py                 # Artifact, ArtifactRef, ArtifactSchema
│   │   ├── task.py                     # TaskNode, TaskStatus, RetryPolicy
│   │   ├── workflow.py                 # WorkflowSpec (parsed from YAML)
│   │   ├── execution.py               # ExecutionRecord, RunSummary
│   │   └── agent.py                   # AgentInfo, AgentHealth
│   │
│   ├── graph/                          # Task Graph Engine (DAG mechanics only)
│   │   ├── dag.py                      # DAG construction + cycle detection
│   │   └── scheduler.py               # ready nodes, dependency satisfaction, parallelism
│   │   # NOTE: scheduler is graph-oriented for MVP. Runtime scheduling
│   │   # concerns (retries, deadlines) may split into runtime/scheduler.py later.
│   │
│   ├── runtime/                        # Orchestration runtime
│   │   ├── orchestrator.py             # load workflow → run DAG → collect results
│   │   ├── dispatcher.py              # dispatch tasks via adapters (moved from graph/)
│   │   ├── lifecycle.py                # task state machine transitions
│   │   └── replay.py                   # replay from node, agent swap (mutating operation)
│   │
│   ├── adapters/                       # Pluggable agent backends
│   │   ├── base.py                     # AgentAdapter protocol
│   │   ├── a2a.py                      # A2AAgentAdapter (Google A2A SDK)
│   │   ├── local.py                    # LocalPythonAdapter (in-process)
│   │   └── llm.py                      # LLMAdapter (direct LiteLLM)
│   │
│   ├── stores/                         # Runtime Stores
│   │   ├── artifact_store.py           # store/get/list artifacts
│   │   ├── execution_store.py          # record/get execution records
│   │   └── backends/
│   │       ├── sqlite.py               # SQLite (default)
│   │       ├── memory.py               # in-memory (tests)
│   │       └── filesystem.py           # filesystem for artifact content
│   │
│   ├── trace/                          # Execution Trace + Lineage (read-only inspection)
│   │   ├── tracer.py                   # trace(run_id) → timeline
│   │   ├── lineage.py                  # artifact lineage chains
│   │   └── diff.py                     # diff two runs (artifact + execution level)
│   │
│   ├── registry/                       # Agent Registry Service (standalone FastAPI)
│   │   ├── __main__.py                 # python -m binex.registry
│   │   ├── app.py                      # FastAPI app
│   │   ├── discovery.py                # crawl Agent Cards + manual registration
│   │   ├── index.py                    # capability index + search
│   │   └── health.py                   # health tracking (alive/slow/degraded/down)
│   │
│   ├── workflow_spec/                  # Workflow definition parsing
│   │   ├── loader.py                   # load YAML/JSON → WorkflowSpec
│   │   └── validator.py                # validate workflow structure
│   │
│   ├── agents/                         # Reference Agents (not part of platform)
│   │   ├── common/
│   │   │   ├── llm_config.py           # LLMConfig + auto-detection
│   │   │   └── llm_client.py           # call_llm() via LiteLLM
│   │   ├── planner/
│   │   │   ├── __main__.py             # python -m binex.agents.planner
│   │   │   ├── agent.py                # AgentExecutor impl
│   │   │   └── prompts.py             # system/user prompts
│   │   ├── researcher/
│   │   │   ├── __main__.py
│   │   │   ├── agent.py
│   │   │   └── prompts.py
│   │   ├── validator/
│   │   │   ├── __main__.py
│   │   │   ├── agent.py
│   │   │   └── prompts.py
│   │   └── summarizer/
│   │       ├── __main__.py
│   │       ├── agent.py
│   │       └── prompts.py
│   │
│   └── cli/                            # CLI entry points
│       ├── __init__.py
│       ├── main.py                     # binex (top-level dispatcher)
│       ├── run.py                      # binex run workflow.yaml
│       ├── trace.py                    # binex trace / trace graph / trace node
│       ├── replay.py                   # binex replay --from / --agent
│       ├── diff.py                     # binex diff run_a run_b
│       ├── artifacts.py                # binex artifacts list/show/lineage
│       ├── dev.py                      # binex dev (local stack)
│       ├── doctor.py                   # binex doctor
│       ├── validate.py                 # binex validate workflow.yaml
│       └── scaffold.py                 # binex scaffold agent
│
├── examples/                           # Workflow examples
│   ├── research.yaml                   # research pipeline (main demo)
│   └── simple.yaml                     # minimal 2-agent example
│
├── tests/
│   ├── unit/
│   │   ├── test_dag.py
│   │   ├── test_scheduler.py
│   │   ├── test_lifecycle.py
│   │   ├── test_artifact_store.py
│   │   ├── test_execution_store.py
│   │   ├── test_replay.py
│   │   ├── test_diff.py
│   │   ├── test_lineage.py
│   │   ├── test_workflow_loader.py
│   │   └── test_adapters.py
│   ├── integration/
│   │   ├── test_orchestrator.py
│   │   ├── test_registry.py
│   │   └── test_pipeline.py
│   └── conftest.py
│
├── docker/
│   ├── Dockerfile                      # multi-stage (agents + registry)
│   └── docker-compose.yml              # full local stack
│
└── .github/
    └── workflows/
        └── ci.yml
```

### 3.2 — Dependency Graph

```
Internal dependency order:

models (zero deps)
  ↓
stores (models)
  ↓
adapters (models)        ← a2a-sdk isolated here
  ↓
graph (models)
  ↓
trace (models, stores)   ← read-only, no runtime deps
  ↓
runtime (graph, stores, adapters, trace)
  ↓
cli (runtime, trace, workflow_spec, registry)

Standalone:
  models → workflow_spec    (YAML parsing)
  models → registry         (FastAPI service)
  models → agents           (A2A servers)
```

**Key rule**: `trace` operates on stores and models only. It must never import from `runtime`. `replay` lives in `runtime/` because it is a mutating orchestration action, not read-only inspection.

### 3.3 — External Dependencies

```toml
[project]
name = "binex"
requires-python = ">=3.11"
dependencies = [
    "a2a-sdk",              # Google A2A Python SDK
    "litellm",              # Ollama/Claude/OpenAI unified
    "fastapi",              # web framework (registry + agents)
    "uvicorn",              # ASGI server
    "httpx",                # async HTTP client
    "pydantic>=2.0",        # data validation
    "pyyaml",               # workflow spec parsing
    "click",                # CLI framework
    "aiosqlite",            # async SQLite (default execution store)
]

[project.optional-dependencies]
postgres = ["asyncpg"]
dev = ["pytest", "pytest-asyncio", "ruff", "mypy"]

[project.scripts]
binex = "binex.cli.main:cli"
```

**Dependency policy**: `a2a-sdk` is used only inside `adapters/a2a.py`. Adding a new dependency requires justification that stdlib or existing deps cannot meet the need.

### 3.4 — Workflow Spec Format

```yaml
# examples/research.yaml
name: research-pipeline
description: "Multi-agent research pipeline"

nodes:
  planner:
    agent: http://localhost:9001    # Binex-resolvable agent endpoint
    skill: planning.research        # may evolve to capability/intent
    inputs:
      query: "${user.query}"
    outputs: [execution_plan]

  researcher_1:
    agent: http://localhost:9002
    skill: research.search
    inputs:
      plan: "${planner.execution_plan}"
      source: arxiv
    outputs: [search_results]
    depends_on: [planner]

  researcher_2:
    agent: http://localhost:9003
    skill: research.search
    inputs:
      plan: "${planner.execution_plan}"
      source: google_scholar
    outputs: [search_results]
    depends_on: [planner]

  validator:
    agent: http://localhost:9004
    skill: analysis.validate
    inputs:
      results:
        - "${researcher_1.search_results}"
        - "${researcher_2.search_results}"
    outputs: [validated_results]
    depends_on: [researcher_1, researcher_2]
    retry_policy:
      max_retries: 2
      backoff: exponential

  summarizer:
    agent: http://localhost:9005
    skill: analysis.summarize
    inputs:
      validated: "${validator.validated_results}"
    outputs: [summary_report]
    depends_on: [validator]
    deadline_ms: 60000

defaults:
  deadline_ms: 120000
  retry_policy:
    max_retries: 1
```

### 3.5 — Key Interfaces

```python
# adapters/base.py
class AgentAdapter(Protocol):
    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]: ...

    async def cancel(self, task_id: str) -> None: ...

    async def health(self) -> AgentHealth: ...
```

```python
# stores/artifact_store.py
class ArtifactStore(Protocol):
    async def store(self, artifact: Artifact) -> ArtifactRef: ...
    async def get(self, artifact_id: str) -> Artifact: ...
    async def list_by_run(self, run_id: str) -> list[Artifact]: ...
    async def get_lineage(self, artifact_id: str) -> LineageTree: ...
```

```python
# stores/execution_store.py
class ExecutionStore(Protocol):
    async def record(self, record: ExecutionRecord) -> str: ...
    async def get_run(self, run_id: str) -> list[ExecutionRecord]: ...
    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None: ...
    async def list_runs(self) -> list[RunSummary]: ...
```

---

## MVP Scope

### Must Have (Phase 1)

- DAG execution + task lifecycle + scheduler
- Typed artifacts + lineage
- Execution store + trace + replay from node
- Agent adapters (A2A + local + LLM)
- Local registry (pull-based)
- 4 reference agents (planner, researcher, validator, summarizer)
- CLI (run, trace, replay, diff, artifacts, dev, doctor, validate)
- Docker Compose + Ollama
- Research pipeline example

### Phase 2

- A2A Gateway (routing, proxy, auth, fallback)
- Policy layer (PII, external network, human approval)
- Human-in-the-loop nodes (approval gates)
- Deterministic execution mode
- Advanced capability-aware routing
- Trace viewer UI

---

## Sources

- [Google A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [A2A GitHub Repository](https://github.com/a2aproject/A2A)
- [Linux Foundation A2A Project](https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents/)
