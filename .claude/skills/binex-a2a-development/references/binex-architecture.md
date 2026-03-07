# Binex Architecture Reference

## Table of Contents
1. [Overview](#overview)
2. [Core Data Model](#core-data-model)
3. [Agent Adapter Contract](#agent-adapter-contract)
4. [Workflow YAML Schema](#workflow-yaml-schema)
5. [CLI Commands](#cli-commands)
6. [Storage Layout](#storage-layout)

## Overview

Binex is a debuggable runtime for A2A (Agent-to-Agent) agents. It orchestrates multi-agent pipelines defined as YAML DAGs, tracks artifacts with lineage, and supports replay/diff for debugging.

**Stack**: Python 3.11+, a2a-sdk, litellm, FastAPI, uvicorn, httpx, Pydantic 2.0+, PyYAML, Click, aiosqlite

## Core Data Model

### Key Entities

| Entity | Purpose |
|--------|---------|
| `WorkflowSpec` | Parsed YAML DAG: nodes, edges, defaults |
| `NodeSpec` | Single node: agent, skill, inputs, outputs, depends_on, retry_policy, deadline |
| `TaskNode` | Runtime node: spec + status + adapter + artifact refs + attempt counter |
| `Artifact` | Typed output with lineage (produced_by, derived_from) |
| `ExecutionRecord` | Per-node metadata: agent, status, latency, prompt, model, tool_calls, error |
| `RunSummary` | Run metadata: status, node counts, fork info |
| `AgentInfo` | Registry entry: endpoint, capabilities, health |

### TaskStatus State Machine

```
requested -> accepted -> running -> completed
                                 -> failed
                                 -> cancelled
                                 -> timed_out
failed -> requested (retry)
```

### AgentHealth

```
alive -> slow -> degraded -> down
```

## Agent Adapter Contract

Protocol all adapters implement:

```python
class AgentAdapter(Protocol):
    async def execute(self, task: TaskNode, input_artifacts: list[Artifact], trace_id: str) -> list[Artifact]: ...
    async def cancel(self, task_id: str) -> None: ...
    async def health(self) -> AgentHealth: ...
```

Three adapter types:
- **A2AAgentAdapter** — remote agents via a2a-sdk (see `references/a2a-sdk-patterns.md`)
- **LocalPythonAdapter** — in-process Python callable
- **LLMAdapter** — direct LLM calls via litellm (see `references/litellm-patterns.md`)

## Workflow YAML Schema

```yaml
name: string
description: string

nodes:
  <node-id>:
    agent: string               # URL or registry ref
    skill: string               # Optional capability ID
    inputs:
      <key>: string             # Static or "${node.output}" interpolation
    outputs: [string]
    depends_on: [string]
    retry_policy:
      max_retries: integer      # Default: 1
      backoff: string           # "fixed" | "exponential"
    deadline_ms: integer

defaults:
  deadline_ms: integer          # Default: 120000
  retry_policy:
    max_retries: integer
    backoff: string
```

Variable interpolation: `${node_id.output_name}`, `${user.key}`

Validation: no cycles, valid refs, valid interpolations, at least one entry node.

## CLI Commands

| Command | Purpose |
|---------|---------|
| `binex run <workflow.yaml>` | Execute workflow |
| `binex trace <run-id>` | Timeline view |
| `binex trace graph <run-id>` | DAG visualization |
| `binex trace node <run-id> <step>` | Step detail |
| `binex replay <run-id> --from <step>` | Replay from step |
| `binex replay <run-id> --agent node=agent` | Swap agent |
| `binex diff <run-a> <run-b>` | Compare runs |
| `binex artifacts list/show/lineage` | Artifact management |
| `binex dev` | Start local stack |
| `binex doctor` | Health check |
| `binex validate <workflow.yaml>` | Validate workflow |
| `binex scaffold agent` | Generate agent boilerplate |
| `binex cancel <run-id>` | Cancel running workflow |

## Storage Layout

### Execution Store (SQLite via aiosqlite)

Tables: `runs`, `execution_records`, `artifacts_meta`

### Artifact Store (Filesystem)

```
.binex/artifacts/{run_id}/{artifact_id}.json
```
