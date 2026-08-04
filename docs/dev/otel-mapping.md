# OTel → Binex Span Mapping

**Branch**: `020-eval-mcp-otel`  
**Purpose**: Defines exactly how OTLP trace data maps onto Binex's native entities (`RunSummary`, `ExecutionRecord`, `Artifact`, `CostRecord`) for `binex import otel` and the live collector.

---

## 1. Overview

```
OTLP ExportTraceServiceRequest
  └── resourceSpans[]
        ├── resource.attributes  (service.name, ...)
        └── scopeSpans[]
              ├── scope.name      (instrumentation library name)
              └── spans[]         → ExecutionRecord + Artifact + CostRecord
```

One **trace** (unique `traceId`) becomes one **`RunSummary`**.  
One **span** becomes one **`ExecutionRecord`**, plus optional `Artifact`s/`CostRecord` when AI semantic convention attributes are present.

---

## 2. Trace → RunSummary

| OTLP field | Binex field | Notes |
|---|---|---|
| `traceId` | `run_id = "otel-" + traceId[:12]` | 12-char hex prefix, prefixed to avoid collisions with native `run_*` IDs |
| root span name or `resource.attributes["service.name"]` | `workflow_name` | Root span name preferred; `service.name` fallback; `"unknown"` as last resort |
| min(span.startTimeUnixNano) | `started_at` | Earliest span start, UTC |
| max(span.endTimeUnixNano) | `completed_at` | Latest span end, UTC |
| span status codes (all spans) | `status` | `"completed"` if all `STATUS_CODE_OK` or `STATUS_CODE_UNSET`; `"failed"` if any `STATUS_CODE_ERROR`; `"partial"` if collector timed out |
| (fixed) | `source = "otel-import"` | Always set; used for feature gating |
| `len(spans)` | `total_nodes` | One node per span |
| count of non-error spans | `completed_nodes` | — |
| count of `STATUS_CODE_ERROR` spans | `failed_nodes` | — |

---

## 3. Span → ExecutionRecord

| OTLP field | Binex field | Notes |
|---|---|---|
| `name` (sanitized) | `task_id` | See §4 for sanitization and deduplication |
| `parentSpanId` → parent span's `task_id` | `parent_task_id` | `None` for root spans |
| `"otel://" + scope.name` | `agent_id` | e.g. `otel://opentelemetry.instrumentation.langchain` |
| `(endTimeUnixNano - startTimeUnixNano) / 1_000_000` | `latency_ms` | Integer milliseconds |
| ISO-8601 UTC from `startTimeUnixNano` | `timestamp` | — |
| `run_id` | `run_id` | From parent RunSummary |
| span status | `status` | `TaskStatus.COMPLETED` or `TaskStatus.FAILED` |
| `status.message` if ERROR | `error` | Error detail string |
| (fixed) | `trace_id = "otel-" + traceId` | For SSE/lineage consistency |

---

## 4. Node-ID Sanitization and Deduplication

Span names are often human-readable but can contain characters invalid in node IDs (spaces, slashes, angle brackets, etc.).

**Sanitization rules** (applied in order):

1. Convert to lower-case.
2. Replace sequences of `[^a-z0-9_\-]` with `_`.
3. Strip leading/trailing underscores.
4. Truncate to 64 characters.
5. If empty after truncation, use `span_<index>`.

**Deduplication**: within a single trace, when two or more spans produce the same sanitized name, suffix the second occurrence with `-2`, the third with `-3`, etc.:

```
"ChatOpenAI" → "chatopenai"
"ChatOpenAI" → "chatopenai-2"   (second span with same name)
```

The mapping from `spanId` → `task_id` is built during a first pass over all spans before any `ExecutionRecord` is created, so `parent_task_id` references use the final deduplicated names.

---

## 5. LLM Span Attributes → Artifacts

Artifacts are only created when the span carries recognized AI semantic convention attributes.  Plain spans (web calls, DB queries, etc.) produce only an `ExecutionRecord`.

### 5.1 OpenInference Conventions (`llm.*`)

Used by LangChain, LlamaIndex, and Arize Phoenix instrumentation.

| Attribute | Artifact |
|---|---|
| `llm.input_messages` (JSON array) | Input artifact, `type="prompt"` |
| `llm.output_messages` (JSON array) | Output artifact, `type="llm_output"` |
| `llm.model_name` | Stored on `CostRecord.model` |
| `llm.token_count.prompt` | Prompt token count for cost calc |
| `llm.token_count.completion` | Completion token count for cost calc |

### 5.2 OpenLLMetry Conventions (`gen_ai.*`)

Used by Traceloop and OpenLLMetry instrumentation.

| Attribute | Artifact |
|---|---|
| `gen_ai.prompt` (string or JSON) | Input artifact, `type="prompt"` |
| `gen_ai.completion` (string or JSON) | Output artifact, `type="llm_output"` |
| `gen_ai.request.model` | Stored on `CostRecord.model` |
| `gen_ai.usage.prompt_tokens` | Prompt token count |
| `gen_ai.usage.completion_tokens` | Completion token count |

Both conventions are checked; OpenInference takes precedence when both are present.

### 5.3 Artifact Shape

```python
Artifact(
    id=f"{task_id}_{'input' | 'output'}",
    type="prompt" | "llm_output",
    content=<string or dict>,
    lineage=Lineage(
        run_id=run_id,
        produced_by=task_id,
        derived_from=[parent_span_task_id + "_output"]  # when parent exists
    ),
)
```

`derived_from` is set to the parent span's output artifact ID when the parent also had an output artifact — this reconstructs the DAG lineage chain.

---

## 6. Cost → CostRecord

Cost is computed with a best-effort cascade:

1. **Explicit span attribute**: `llm.token_count.total_cost` or `gen_ai.usage.total_cost` → use directly.
2. **Token counts + model**: pass to `litellm.completion_cost(model, prompt_tokens, completion_tokens)`.  If litellm does not recognise the model, this returns 0 and the source is set accordingly.
3. **No attributes**: no `CostRecord` is created for this span.

```python
CostRecord(
    run_id=run_id,
    node_id=task_id,
    model=model_name,
    cost=computed_cost,
    source="otel-import" | "llm_tokens_unavailable",
    prompt_tokens=...,
    completion_tokens=...,
)
```

`source="llm_tokens_unavailable"` follows the pattern established in the native cost tracker when `litellm.completion_cost()` cannot determine a price.

---

## 7. DAG Derivation from parentSpanId

The parent–child relationship between spans directly encodes the DAG:

```
root span (parentSpanId absent / all-zeros)
  ├── child A (parentSpanId = root.spanId)
  │     └── grandchild A1
  └── child B
```

This maps to:

```
ExecutionRecord(task_id="root", parent_task_id=None)
ExecutionRecord(task_id="child_a", parent_task_id="root")
ExecutionRecord(task_id="grandchild_a1", parent_task_id="child_a")
ExecutionRecord(task_id="child_b", parent_task_id="root")
```

`parent_task_id` is already defined on `ExecutionRecord` (added in 018-loop-container) and is used by the lineage viewer.

---

## 8. Orphan Spans and Multi-Root Handling

Real traces sometimes contain spans whose `parentSpanId` does not appear in the trace (orphans), or multiple spans with no parent (multi-root).

**Strategy**:

- **Orphans**: attached as top-level nodes (`parent_task_id=None`). A non-fatal warning is added to the import result: `"Orphan spans attached as roots: [<task_ids>]"`.
- **Multiple roots**: all root spans are kept. The `workflow_name` is taken from the *first* root span (by start time) or `service.name`. A warning is emitted: `"Multiple root spans detected: [<task_ids>]"`.
- **Empty spans list**: the trace is skipped; a warning is emitted.

Warnings are collected in a `list[str]` and returned alongside the `RunSummary` by the converter so callers (CLI, collector) can surface them.

---

## 9. source = "otel-import" Feature Gate

Any `RunSummary` with `source="otel-import"` is blocked from:

- `binex replay` (CLI exit 2, message: *"Run '<id>' was imported from an external trace and cannot be replayed."*)
- `binex bisect` (CLI exit 2 for either run being imported)
- `POST /api/v1/replay` (HTTP 422)
- `POST /api/v1/bisect` (HTTP 422)
- `mcp replay_node` tool (returns `{"error": ..., "code": "unsupported"}`)

**Not blocked**: `binex debug`, `binex trace`, `binex diagnose`, `binex diff`, `binex artifacts`, the Web UI RunDetail/Trace/Lineage views.  These operate purely on stored records and artifacts and work identically for imported runs.

The shared helper is `ensure_replayable(run: RunSummary) -> None` (raises `ImportedRunError`) located in `src/binex/runtime/replay.py`.

---

## 10. Collector Buffering State Machine

```
Span arrives via POST /v1/traces
  → add to TraceBuffer[trace_id]
  → start/reset quiet timer (10 s default)

Quiet timer fires AND root span present
  → finalize: run converter → write to stores → run visible in UI

Hard timeout (300 s) fires regardless
  → finalize with status="partial" + warning logged
```

Each `TraceBuffer` tracks:
- `spans: list[dict]` — raw span dicts
- `root_seen: bool` — whether any span with no parent has been received
- `resource: dict` — merged resource attributes
- `last_activity: float` — wall-clock time of last span receipt

The converter is the same function as for file import (`importers/otel.py`) — no duplication.
