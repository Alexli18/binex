# Implementation Plan: Binex Runtime

**Branch**: `001-binex-runtime` | **Date**: 2026-03-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-binex-runtime/spec.md`

## Summary

Binex is a debuggable runtime for A2A agents. It provides DAG-based workflow execution with typed artifact lineage, execution tracing, and time-travel replay. Built as a single Python package (`pip install binex`), it orchestrates any A2A-compatible agent through pluggable adapters and exposes all functionality via a CLI. The MVP delivers a complete research pipeline demo with 4 reference agents running locally via Docker Compose + Ollama.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: a2a-sdk, litellm, fastapi, uvicorn, httpx, pydantic 2.0+, pyyaml, click, aiosqlite
**Storage**: SQLite (execution store, default), filesystem (artifact store, default), in-memory (tests)
**Testing**: pytest, pytest-asyncio, ruff (linting), mypy (type checking)
**Target Platform**: Linux/macOS (CLI + Docker)
**Project Type**: CLI + library + microservices (reference agents + registry)
**Performance Goals**: 5-node pipeline completes in reasonable time; parallel nodes reduce wall time by 30%+
**Constraints**: Single Python package, A2A SDK isolated to adapter layer, zero circular dependencies
**Scale/Scope**: Single-user local usage (MVP), pipelines up to 20 nodes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution is not yet defined for this project (template only). No gates to evaluate. Proceeding with standard software engineering best practices:

- Single package structure (no unnecessary abstraction)
- Dependency isolation (A2A SDK only in adapters/)
- Layered architecture with clear dependency direction (models -> stores -> adapters -> graph -> trace -> runtime -> cli)
- Test coverage for core logic (DAG, scheduler, lifecycle, stores, replay, diff)

**Post-Phase 1 re-check**: Design adheres to all principles from the design document. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-binex-runtime/
├── plan.md              # This file
├── research.md          # Phase 0: Technology decisions
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Getting started guide
├── contracts/           # Phase 1: Interface contracts
│   ├── cli.md           # CLI command structure
│   ├── agent-adapter.md # Adapter protocol + registry API
│   └── workflow-spec.md # Workflow YAML schema
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/binex/
├── __init__.py
├── settings.py
├── models/                    # Domain models (zero internal deps)
│   ├── artifact.py            # Artifact, ArtifactRef, Lineage
│   ├── task.py                # TaskNode, TaskStatus, RetryPolicy
│   ├── workflow.py            # WorkflowSpec, NodeSpec, DefaultsSpec
│   ├── execution.py           # ExecutionRecord, RunSummary
│   └── agent.py               # AgentInfo, AgentHealth
├── graph/                     # DAG engine
│   ├── dag.py                 # DAG construction + cycle detection
│   └── scheduler.py           # Ready nodes, dependency tracking
├── runtime/                   # Orchestration
│   ├── orchestrator.py        # Workflow -> DAG -> execute -> results
│   ├── dispatcher.py          # Task dispatch via adapters
│   ├── lifecycle.py           # State machine transitions
│   └── replay.py              # Replay from step, agent swap
├── adapters/                  # Agent backends
│   ├── base.py                # AgentAdapter protocol
│   ├── a2a.py                 # A2A SDK adapter
│   ├── local.py               # In-process adapter
│   └── llm.py                 # Direct LLM adapter
├── stores/                    # Persistence
│   ├── artifact_store.py      # Artifact store protocol
│   ├── execution_store.py     # Execution store protocol
│   └── backends/
│       ├── sqlite.py          # SQLite backend
│       ├── memory.py          # In-memory backend (tests)
│       └── filesystem.py      # Filesystem artifact storage
├── trace/                     # Read-only inspection
│   ├── tracer.py              # Timeline generation
│   ├── lineage.py             # Artifact provenance chains
│   └── diff.py                # Run comparison
├── registry/                  # Agent registry (FastAPI)
│   ├── __main__.py
│   ├── app.py
│   ├── discovery.py
│   ├── index.py
│   └── health.py
├── workflow_spec/             # Workflow parsing
│   ├── loader.py
│   └── validator.py
├── agents/                    # Reference agents
│   ├── common/
│   │   ├── llm_config.py
│   │   └── llm_client.py
│   ├── planner/
│   ├── researcher/
│   ├── validator/
│   └── summarizer/
└── cli/                       # CLI entry points
    ├── __init__.py
    ├── main.py
    ├── run.py
    ├── trace.py
    ├── replay.py
    ├── diff.py
    ├── artifacts.py
    ├── dev.py
    ├── doctor.py
    ├── validate.py
    └── scaffold.py

tests/
├── conftest.py
├── unit/
│   ├── test_dag.py
│   ├── test_scheduler.py
│   ├── test_lifecycle.py
│   ├── test_artifact_store.py
│   ├── test_execution_store.py
│   ├── test_replay.py
│   ├── test_diff.py
│   ├── test_lineage.py
│   ├── test_workflow_loader.py
│   └── test_adapters.py
└── integration/
    ├── test_orchestrator.py
    ├── test_registry.py
    └── test_pipeline.py

examples/
├── research.yaml
└── simple.yaml

docker/
├── Dockerfile
└── docker-compose.yml
```

**Structure Decision**: Single Python package (`src/binex/`) following the design document layout. Layered architecture with strict dependency direction: models (zero deps) -> stores/adapters/graph -> trace -> runtime -> cli. Tests mirror the source structure with unit and integration separation.

## Complexity Tracking

No constitution violations to justify. Architecture follows the design document directly.
