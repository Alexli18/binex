# binex-trace SDK

binex-trace emits structured JSON events to stderr, enabling observability for A2A agents without runtime dependencies. Events are parsed by binex from agent stderr output and stored alongside execution records.

## Installation

Two ways to use it:

**Option 1 — Standalone package (zero deps):**
```bash
pip install binex-trace
```

**Option 2 — Built-in fallback (no install needed):**
```python
from binex.trace import trace  # works without binex-trace installed
```

The built-in fallback is always available when running inside a binex workflow. Use the standalone package for agents that run outside binex.

## API

### trace.task(name)

Decorator. Wraps a function, emits `task_start` on entry and `task_end` on exit with status and duration.

```python
from binex.trace import trace

@trace.task("process_data")
def process(data):
    # ... your code
    return result
```

Async functions are supported — binex-trace detects `async def` and awaits automatically.

### trace.log(message, **kwargs)

Emit a log event within the current task. Extra kwargs are included in the event.

```python
trace.log("loaded 1000 records", source="db")
```

### trace.checkpoint(data, label="checkpoint")

Save a checkpoint. Survives crash if stderr is captured before the process exits.

```python
trace.checkpoint({"step": 3, "accuracy": 0.95}, label="training")
```

## Event Schema

All events are JSON objects emitted to stderr with `"_binex_trace": true` as a marker. Binex identifies trace events by this field and ignores other stderr output.

### task_start

```json
{"_binex_trace": true, "type": "task_start", "ts": 1711234567.89, "name": "process_data", "args_repr": "('input',)"}
```

### task_end

```json
{"_binex_trace": true, "type": "task_end", "ts": 1711234568.12, "name": "process_data", "status": "ok", "duration_s": 0.23}
```

On error, `status` is `"error"` and an `error` field is added:

```json
{"_binex_trace": true, "type": "task_end", "ts": 1711234568.12, "name": "process_data", "status": "error", "duration_s": 0.23, "error": "ValueError: unexpected input"}
```

### log

```json
{"_binex_trace": true, "type": "log", "ts": 1711234567.95, "message": "loaded 1000 records", "source": "db"}
```

### checkpoint

```json
{"_binex_trace": true, "type": "checkpoint", "ts": 1711234568.0, "label": "training", "data_preview": "{'step': 3, ...}"}
```

`data_preview` is a truncated `repr()` of `data`. The full value is not stored — checkpoints are for crash recovery and progress tracking, not data transfer.

### Event Fields Reference

| Field | Present On | Description |
|---|---|---|
| `_binex_trace` | all | Always `true`. Used by binex to identify trace events. |
| `type` | all | `task_start`, `task_end`, `log`, or `checkpoint` |
| `ts` | all | Unix timestamp (float, seconds) |
| `name` | `task_start`, `task_end` | Function name passed to `@trace.task()` |
| `args_repr` | `task_start` | `repr()` of positional args (truncated) |
| `status` | `task_end` | `"ok"` or `"error"` |
| `duration_s` | `task_end` | Wall-clock seconds the function took |
| `error` | `task_end` (errors only) | `"{ExceptionType}: {message}"` |
| `message` | `log` | Log message string |
| `label` | `checkpoint` | Checkpoint label (default `"checkpoint"`) |
| `data_preview` | `checkpoint` | Truncated `repr()` of checkpoint data |

## CLI Integration

```bash
# View subtask tree from captured stderr
binex trace subtasks agent_stderr.log

# View trace events in node detail
binex trace node <run_id> <step>
```

Output:

```
├─ process_data     ✅ 0.23s
│  └─ log: "loaded 1000 records"
├─ validate         ✅ 0.05s
│  └─ checkpoint: "validation"
└─ export           ❌ timeout (30.0s)
```

See [binex trace CLI](../cli/trace.md) for full command reference.

## How It Works

1. Agent code uses `trace.task()`, `trace.log()`, `trace.checkpoint()`
2. Events are printed as JSON lines to stderr
3. Binex captures agent stderr during execution
4. `parse_trace_events()` scans each line, extracts objects with `_binex_trace: true`
5. Events are stored in the `trace_events` column of execution records (SQLite)
6. `binex trace node` and `binex trace subtasks` read from SQLite and render the tree

No sidecar process, no network calls, no runtime dependencies. If binex is not capturing stderr, events are silently emitted and discarded — the agent continues to work normally.

## See Also

- [binex trace CLI](../cli/trace.md)
- [Telemetry (OpenTelemetry)](../architecture/telemetry.md)
- [binex-trace on GitHub](https://github.com/Alexli18/binex-trace)
