# Runtime

## Overview

The runtime layer contains the **Orchestrator** and **Dispatcher** -- the two
components that drive workflow execution. The Orchestrator owns the execution
loop: it builds a DAG from the workflow spec, uses the Scheduler to determine
ready nodes, and delegates each task to the Dispatcher. The Dispatcher maps
agent keys to registered adapters and forwards calls.

## Components

| Component      | Module                       | Role                                      |
|----------------|------------------------------|--------------------------------------------|
| Orchestrator   | `runtime/orchestrator.py`    | Top-level execution loop, records results  |
| Dispatcher     | `runtime/dispatcher.py`      | Agent registry, routes tasks to adapters   |
| DAG            | `graph/dag.py`               | Dependency graph built from WorkflowSpec   |
| Scheduler      | `graph/scheduler.py`         | Tracks node states, yields ready nodes     |

## Interfaces

```python
class Orchestrator:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        execution_store: ExecutionStore,
    ) -> None: ...

    async def run_workflow(
        self,
        workflow: dict[str, Any] | WorkflowSpec,
        *,
        user_vars: dict[str, str] | None = None,
    ) -> RunSummary: ...
```

```python
class Dispatcher:
    def __init__(self) -> None: ...

    def register_adapter(self, agent_key: str, adapter: AgentAdapter) -> None: ...
    def get_adapter(self, agent_key: str) -> AgentAdapter: ...

    async def dispatch(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]: ...
```

```python
class Scheduler:
    def __init__(self, dag: DAG) -> None: ...

    def ready_nodes(self) -> list[str]: ...
    def mark_running(self, node_id: str) -> None: ...
    def mark_completed(self, node_id: str) -> None: ...
    def mark_failed(self, node_id: str) -> None: ...
    def is_complete(self) -> bool: ...
    def is_blocked(self) -> bool: ...
```

## Data Flow

```
run_workflow(spec, user_vars)
    |
    v
+-- WorkflowSpec parsed (${user.*} vars resolved) ------+
|                                                        |
|   DAG.from_workflow(spec) ----> DAG instance           |
|                |                                       |
|                v                                       |
|         Scheduler(dag)                                 |
|                |                                       |
|   +============|=== execution loop =================+  |
|   |            v                                    |  |
|   |   ready_nodes() ---> [node_a, node_b, ...]      |  |
|   |        |                                        |  |
|   |        v                                        |  |
|   |   mark_running(node_id)                         |  |
|   |        |                                        |  |
|   |        v                                        |  |
|   |   Dispatcher.dispatch(task, artifacts, trace)    |  |
|   |        |                                        |  |
|   |        +---> adapter.execute() --> [Artifact]    |  |
|   |        |                                        |  |
|   |        v                                        |  |
|   |   ArtifactStore.store(artifact)                  |  |
|   |   ExecutionStore.record(execution_record)        |  |
|   |        |                                        |  |
|   |        v                                        |  |
|   |   mark_completed(node_id) or mark_failed()       |  |
|   |        |                                        |  |
|   |        +---> loop until is_complete()            |  |
|   |                                                  |  |
|   +==================================================+  |
|                |                                       |
|                v                                       |
|         RunSummary returned                            |
+--------------------------------------------------------+
```
