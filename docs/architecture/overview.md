# Architecture Overview

## Overview

Binex is a debuggable runtime for AI agent workflows. It executes DAG-based
workflows where each node delegates to an **adapter** (LLM, A2A remote agent,
or local Python function). Every execution step is recorded to persistent
stores, enabling full replay and tracing.

## Components

The codebase follows a strict layered dependency structure. Each layer may only
import from layers below it.

```
+-------------------------------------------------------------+
|                          cli                                 |
|  main.py  run.py  replay.py  dev.py                         |
+-------------------------------------------------------------+
|                      orchestrator                            |
|  runtime/orchestrator.py                                     |
+-------------------------------------------------------------+
|                       dispatcher                             |
|  runtime/dispatcher.py                                       |
+---------------------------+---------------------------------+
|       adapters            |            graph                 |
|  adapters/base.py         |  graph/dag.py                   |
|  adapters/llm.py          |  graph/scheduler.py             |
|  adapters/a2a.py          |                                  |
|  adapters/local.py        |                                  |
+---------------------------+---------------------------------+
|                        stores                                |
|  stores/execution_store.py   stores/artifact_store.py        |
|  stores/backends/sqlite.py   stores/backends/filesystem.py   |
+-------------------------------------------------------------+
|                        models                                |
|  models/workflow.py  (WorkflowSpec, NodeSpec)                |
|  models/task.py      (TaskNode, Artifact, ExecutionRecord)   |
|  models/health.py    (AgentHealth, RunSummary)               |
+-------------------------------------------------------------+
```

## Interfaces

The two foundational protocols that all upper layers depend on:

```python
class ExecutionStore(Protocol):
    async def record(self, execution_record: ExecutionRecord) -> None: ...
    async def list_records(self, run_id: str) -> list[ExecutionRecord]: ...

class ArtifactStore(Protocol):
    async def store(self, artifact: Artifact) -> None: ...
    async def get(self, artifact_id: str) -> Artifact | None: ...
```

The adapter contract that every agent type implements:

```python
class AgentAdapter(Protocol):
    async def execute(self, task: TaskNode, input_artifacts: list[Artifact], trace_id: str) -> list[Artifact]: ...
```

## Data Flow

```
YAML file
    |
    v
WorkflowSpec ----> DAG.from_workflow() ----> DAG
    |                                         |
    v                                         v
Orchestrator.run_workflow()             Scheduler
    |                                         |
    |   +------ ready_nodes() <---------------+
    |   |
    v   v
Dispatcher.dispatch(task, artifacts, trace_id)
    |
    v
AgentAdapter.execute()  --->  list[Artifact]
    |                              |
    v                              v
ExecutionStore.record()    ArtifactStore.store()
    |                              |
    v                              v
.binex/binex.db            .binex/artifacts/{run_id}/{id}.json
```
