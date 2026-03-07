---
name: binex-a2a-development
description: |
  Develop the Binex debuggable runtime for A2A (Agent-to-Agent) agents. Use when implementing Binex components: DAG workflow orchestration, agent adapters (A2A, local Python, LLM via litellm), artifact store with lineage tracking, execution store (aiosqlite), CLI commands (Click), workflow YAML parsing/validation, replay/diff, agent registry, or reference agents. Triggers: "binex", "a2a agent adapter", "workflow DAG", "artifact lineage", "execution trace", "replay run", "agent registry", "LLMAdapter", "A2AAgentAdapter", "LocalPythonAdapter", "binex run", "binex trace", "binex replay", "binex diff", "binex scaffold".
---

# Binex A2A Development

Build the Binex runtime — a debuggable orchestrator for A2A agent pipelines.

## Stack

Python 3.11+, a2a-sdk, litellm, FastAPI, uvicorn, httpx, Pydantic 2.0+, PyYAML, Click, aiosqlite

## Project Layout

```
src/
  binex/
    cli/           # Click commands
    core/          # WorkflowSpec, NodeSpec, TaskNode, DAG parser, scheduler, interpolation
    adapters/      # AgentAdapter protocol + A2AAgentAdapter, LocalPythonAdapter, LLMAdapter
    stores/        # ArtifactStore (filesystem), ExecutionStore (aiosqlite)
    registry/      # AgentInfo, health checks, capability search (FastAPI)
    models/        # Pydantic models: Artifact, ExecutionRecord, RunSummary, Lineage
tests/
```

## Key Contracts

### AgentAdapter Protocol

```python
class AgentAdapter(Protocol):
    async def execute(
        self, task: TaskNode, input_artifacts: list[Artifact], trace_id: str
    ) -> list[Artifact]: ...
    async def cancel(self, task_id: str) -> None: ...
    async def health(self) -> AgentHealth: ...
```

Three implementations:
- **A2AAgentAdapter** — remote via a2a-sdk. See `references/a2a-sdk-patterns.md`
- **LocalPythonAdapter** — in-process callable
- **LLMAdapter** — direct LLM via litellm. See `references/litellm-patterns.md`

### TaskStatus State Machine

```
requested -> accepted -> running -> completed | failed | cancelled | timed_out
failed -> requested (retry)
```

### Workflow YAML

Nodes with `agent`, `skill`, `inputs` (`${node.output}` interpolation), `outputs`, `depends_on`, `retry_policy`, `deadline_ms`. Full schema in `references/binex-architecture.md`.

## Implementation Guidelines

### Pydantic Models

Pydantic 2.0+ with `model_config(from_attributes=True)`. Use `X | None` not `Optional[X]`. All entities are BaseModel subclasses.

### Async Everywhere

All I/O is async: aiosqlite for execution store, httpx for A2A calls, `litellm.acompletion` for LLM. Use `asyncio.gather` for parallel DAG nodes.

### DAG Scheduler

Parse YAML -> topological sort -> run independent nodes via `asyncio.gather`. Track per-node status. Handle retries (exponential/fixed backoff), deadlines (`asyncio.wait_for`), cancellation.

### Artifact Lineage

Every Artifact has `Lineage(produced_by=node_id, derived_from=[upstream_ids])`. Metadata in SQLite, content as `.binex/artifacts/{run_id}/{artifact_id}.json`.

### CLI (Click)

Entry: `binex`. Commands: run, trace, replay, diff, artifacts, dev, doctor, validate, scaffold, cancel. `--json` flag for machine output. Exit codes: 0=ok, 1=failed, 2=invalid.

### Testing

Mock LLM at HTTP level (respx). In-memory SQLite for stores. Test adapters in isolation.

## References

| File | Load When |
|------|-----------|
| `references/a2a-sdk-patterns.md` | Implementing A2AAgentAdapter, agent server, agent card, streaming |
| `references/litellm-patterns.md` | Implementing LLMAdapter, async completion, model strings |
| `references/binex-architecture.md` | Full data model, workflow schema, CLI commands, storage layout |
