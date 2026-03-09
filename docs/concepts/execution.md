# Execution

## What is an Execution?

```python
class TaskStatus(enum.StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"

class ExecutionRecord(BaseModel):
    id: str
    run_id: str
    task_id: str
    agent_id: str
    status: TaskStatus
    input_artifact_refs: list[str]
    output_artifact_refs: list[str]
    latency_ms: int
    trace_id: str
    error: str | None = None
```

An execution record captures everything that happened when a node ran: which agent handled it, what went in, what came out, how long it took, and whether it succeeded or failed.

## How It Works

The task lifecycle follows a fixed state progression:

```
requested → accepted → running → completed
                         ↓
                  failed / timed_out / cancelled
```

When the runtime dispatches a node to its [agent](agents.md), it creates an `ExecutionRecord` in `REQUESTED` status. The adapter accepts the task, transitions it to `RUNNING`, and on completion writes the final status (`COMPLETED` or `FAILED`). If the node exceeds its `deadline_ms`, the status becomes `TIMED_OUT`.

Execution records are persisted in `.binex/binex.db` (SQLite) via `SqliteExecutionStore`. Each record links to its [artifacts](artifacts.md) through `input_artifact_refs` and `output_artifact_refs`, and is grouped by `run_id` and `trace_id` for replay and debugging.

## Example

Query past executions from the CLI:

```bash
binex replay list
binex replay show <run-id>
```

The `replay` commands read from the SQLite store and display the execution history with status, latency, and error details.

## Related Concepts

- [Workflows](workflows.md) -- each workflow run produces execution records
- [Artifacts](artifacts.md) -- execution records reference input and output artifacts
- [Lineage](lineage.md) -- lineage traces which execution produced each artifact
