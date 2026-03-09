# Development Setup

## Prerequisites

- Python 3.11+

## Clone & Install

```bash
git clone <repo>
cd binex
pip install -e ".[dev]"

# Optional: colored debug output
pip install -e ".[rich]"
```

## Project Structure

```
src/binex/
├── __init__.py
├── settings.py
├── models/          # Pydantic domain models
│   ├── artifact.py  # Artifact, Lineage
│   ├── execution.py # ExecutionRecord, RunSummary
│   ├── task.py      # TaskNode, TaskStatus, RetryPolicy
│   ├── workflow.py  # WorkflowSpec, NodeSpec, DefaultsSpec
│   └── agent.py     # AgentHealth
├── stores/          # Persistence protocols + backends
│   ├── execution_store.py  # ExecutionStore protocol
│   ├── artifact_store.py   # ArtifactStore protocol
│   └── backends/
│       ├── sqlite.py       # SqliteExecutionStore
│       ├── filesystem.py   # FilesystemArtifactStore
│       └── memory.py       # InMemoryExecutionStore, InMemoryArtifactStore
├── adapters/        # Agent execution backends
│   ├── base.py      # AgentAdapter protocol
│   ├── local.py     # LocalPythonAdapter
│   ├── llm.py       # LLMAdapter (via litellm)
│   └── a2a.py       # A2AAgentAdapter (HTTP)
├── graph/           # DAG construction and scheduling
│   ├── dag.py       # DAG, CycleError
│   └── scheduler.py # Scheduler
├── runtime/         # Workflow execution
│   ├── orchestrator.py # Orchestrator
│   ├── dispatcher.py   # Dispatcher
│   ├── replay.py       # ReplayEngine
│   └── lifecycle.py    # Lifecycle utilities
├── workflow_spec/   # YAML loading and validation
│   ├── loader.py    # load_workflow()
│   └── validator.py # validate_workflow()
├── trace/           # Execution inspection
│   ├── tracer.py    # Timeline generation
│   ├── lineage.py   # Lineage tree
│   ├── diff.py      # Run comparison
│   ├── debug_report.py  # Debug report model + builder + formatters
│   └── debug_rich.py    # Rich-formatted debug output (optional dep)
├── registry/        # Agent registry service
│   ├── app.py       # FastAPI app
│   ├── discovery.py # Agent discovery
│   ├── health.py    # Health checking
│   └── index.py     # Agent index
├── agents/          # Built-in A2A agents
│   ├── common/      # Shared LLM client/config
│   ├── planner/
│   ├── researcher/
│   ├── validator/
│   └── summarizer/
└── cli/             # Click CLI commands
    ├── main.py      # Entry point, .env loading
    ├── run.py        # run, cancel
    ├── debug.py      # debug (post-mortem inspection)
    ├── trace.py      # trace group
    ├── replay.py     # replay
    ├── diff.py       # diff
    ├── artifacts.py  # artifacts group
    ├── dev.py        # dev (Docker Compose)
    ├── doctor.py     # doctor (health checks)
    ├── validate.py   # validate
    └── scaffold.py   # scaffold group
```

Layered dependency order: `models` -> `stores` -> `adapters/graph/workflow_spec` -> `trace` -> `runtime` -> `cli`. Do not introduce upward imports.

## Running

```bash
# Execute a workflow
binex run examples/simple.yaml --var input="hello"

# Check environment health
binex doctor
```

Data is persisted under `.binex/` (gitignored): `binex.db` (sqlite) and `artifacts/` (JSON files).

## Code Style

Linter is **ruff**, type checker is **mypy** (strict mode).

```bash
ruff check src/
mypy src/
```

Ruff config: target `py311`, line-length `99`, rule sets `E, F, I, N, W, UP`.
