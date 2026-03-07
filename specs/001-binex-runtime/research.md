# Research: Binex Runtime

**Date**: 2026-03-07
**Feature**: 001-binex-runtime
**Source**: Design document `docs/plans/2026-03-07-binex-design.md`

## R-001: DAG Execution Engine

**Decision**: Custom async DAG executor with topological scheduling.

**Rationale**: The core requirement is executing task nodes in dependency order with parallel execution of independent nodes. Standard workflow engines (Airflow, Prefect) are too heavy and server-oriented. A lightweight in-process DAG executor fits the "single Python package" constraint and allows tight integration with the artifact/trace system.

**Alternatives considered**:
- Airflow/Prefect: Too heavy, server-oriented, not embeddable as a library
- NetworkX for DAG operations + custom scheduler: Viable but NetworkX is an unnecessary dependency; cycle detection and topological sort are straightforward to implement
- asyncio.TaskGroup only: Insufficient — no dependency tracking or retry logic

## R-002: Agent Communication Protocol

**Decision**: Google A2A SDK as the primary inter-agent protocol, isolated behind an adapter interface.

**Rationale**: A2A is an emerging standard backed by Google and Linux Foundation. Using it positions Binex in the A2A ecosystem. The adapter pattern allows supporting non-A2A agents (local Python, direct LLM) without coupling the core to the SDK.

**Alternatives considered**:
- Custom protocol: Would limit ecosystem compatibility
- OpenAI Assistants API: Proprietary, vendor lock-in
- LangChain/LangGraph: Framework lock-in, not a protocol

## R-003: Artifact Storage

**Decision**: Filesystem-based artifact store (default), with protocol for alternative backends (S3, in-memory for tests).

**Rationale**: Artifacts can be large (research reports, data files). Filesystem storage is simple, inspectable, and sufficient for local/single-user usage. The protocol interface allows swapping backends for production.

**Alternatives considered**:
- SQLite BLOBs: Size limitations, harder to inspect
- Pure in-memory: Not persistent across runs
- Object storage only (S3): Requires infrastructure, not suitable for local dev

## R-004: Execution Store

**Decision**: SQLite (via aiosqlite) as default execution store backend.

**Rationale**: SQLite is zero-config, embedded, and sufficient for single-user local usage. Async access via aiosqlite. The protocol interface allows Postgres/DuckDB backends for production.

**Alternatives considered**:
- Postgres-first: Requires running a database server, too heavy for local dev
- DuckDB: Good for analytics but less mature async support
- JSON files: No querying capability, poor for trace/replay operations

## R-005: LLM Abstraction

**Decision**: LiteLLM for unified LLM access across providers (Ollama, OpenAI, Anthropic, etc.).

**Rationale**: LiteLLM provides a single interface to 100+ LLM providers. Critical for local development with Ollama and flexibility to use cloud providers. Already well-established in the ecosystem.

**Alternatives considered**:
- Direct Ollama client: Would limit to local models only
- OpenAI SDK: Would require per-provider integration
- Custom abstraction: Unnecessary when LiteLLM exists

## R-006: CLI Framework

**Decision**: Click as the CLI framework.

**Rationale**: Click is mature, well-documented, supports nested command groups (needed for `binex trace graph`, `binex artifacts lineage`, etc.), and is widely used in the Python ecosystem. The command structure maps cleanly to Click groups.

**Alternatives considered**:
- argparse: Verbose, poor support for nested commands
- Typer: Built on Click, adds type hints but not necessary
- Rich CLI: Presentation layer, not a CLI framework (can be used alongside Click)

## R-007: Workflow Definition Format

**Decision**: YAML as the primary workflow definition format, with JSON as an alternative.

**Rationale**: YAML is human-readable, widely adopted for declarative configurations. The workflow spec includes variable interpolation (`${node.output}`) for artifact references between nodes. PyYAML handles parsing.

**Alternatives considered**:
- Python DSL: Requires code execution, not declarative
- TOML: Poor support for nested/complex structures
- Custom DSL: Unnecessary learning curve

## R-008: Web Framework for Registry

**Decision**: FastAPI for the agent registry service.

**Rationale**: FastAPI provides async support, automatic OpenAPI docs, Pydantic integration for data validation, and is the standard choice for async Python web services. The registry is a standalone service with REST endpoints.

**Alternatives considered**:
- Flask: Synchronous, less suitable for async agent health checks
- Starlette: FastAPI is built on it and adds useful features
- gRPC: Overkill for a local registry service

## R-009: Replay Strategy

**Decision**: Replay creates a new immutable run, linking to cached artifacts from the original run for skipped steps.

**Rationale**: Immutability of runs is critical for auditability and diff operations. Linking rather than copying cached artifacts avoids storage duplication. The new run records which artifacts are reused vs. freshly computed.

**Alternatives considered**:
- Mutating the original run: Violates immutability, breaks diff/audit
- Full re-execution: Wastes time and resources on unchanged upstream steps
- Copy-on-write artifacts: Unnecessary complexity when linking suffices

## R-010: Project Packaging

**Decision**: Single Python package `binex` with hatchling build backend, managed by uv.

**Rationale**: A single package avoids monorepo overhead. `pip install binex` gives users everything. Hatchling is modern and well-integrated with the Python packaging ecosystem. uv for fast dependency resolution.

**Alternatives considered**:
- Monorepo with multiple packages: Premature for MVP
- setuptools: Older, more verbose configuration
- Poetry: Less standard, different lock file format
