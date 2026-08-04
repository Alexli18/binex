# Import from OpenTelemetry

Binex can ingest **existing OpenTelemetry traces** from LangChain, LlamaIndex, and other instrumented apps — no workflow YAML, no migration. Imported runs appear in the web UI and CLI with the same debug, trace, lineage, and diff tools you use for native runs.

## Overview

When you instrument a Python application with OpenLLMetry or OpenInference, it emits OTLP spans that describe each LLM call. Binex can consume those spans two ways:

- **File import** (`binex import otel <file.json>`) — post-mortem analysis of a saved trace file.
- **Live collector** (`binex collect`) — a local OTLP/HTTP endpoint that receives spans as your app runs and finalises them into runs automatically.

Either way, each trace becomes one Binex run (`source="otel-import"`). You get a run ID, per-node latency, token counts, cost estimates, prompt/completion artifacts, and the full lineage chain — without touching your existing code beyond adding the OTEL environment variables.

## Debug Your LangChain App in Binex in 5 Minutes

### 1. Install OpenLLMetry

```bash
pip install traceloop-sdk
```

OpenLLMetry auto-instruments LangChain, LlamaIndex, OpenAI, and other popular libraries with no code changes.

### 2. Configure the OTLP exporter

Set these environment variables before running your app:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
```

Or add them to your `.env` file if you use `python-dotenv`.

### 3. Start the Binex collector

In a separate terminal, from your project root:

```bash
binex collect
```

The collector listens on `http://localhost:4318` and matches the endpoint you configured above.

### 4. Run your app

```bash
python my_langchain_app.py
```

Spans arrive at the collector. Once the trace is quiet for 10 seconds (or your app process exits), Binex finalises the run.

### 5. Open Binex UI

```bash
binex ui
```

Navigate to **Dashboard** — your run appears with node names derived from LangChain span names, per-call latencies, token counts, and cost estimates. Click any node for inputs, outputs, and the full prompt.

## File Import

If you have an existing OTLP JSON export, import it directly:

```bash
binex import otel trace.json
```

Output:

```
Run ID:       otel-3f7a2c1b8e4d
Workflow:     langchain_agent
Nodes:        12
Warnings:     0
```

Use `--json` for machine-readable output:

```bash
binex import otel trace.json --json
```

```json
{
  "run_id": "otel-3f7a2c1b8e4d",
  "workflow_name": "langchain_agent",
  "node_count": 12,
  "warning_count": 0,
  "warnings": [],
  "artifact_count": 24,
  "cost_record_count": 8
}
```

The file must be a valid OTLP `ExportTraceServiceRequest` JSON (the format produced by `OTEL_EXPORTER_OTLP_PROTOCOL=http/json`). One run is created per trace in the file (most exports contain a single trace).

## Live Collector

```
binex collect [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--port` | `4318` | Port to listen on |
| `--host` | `127.0.0.1` | Host to bind to |
| `--quiet-period N` | `10` | Seconds of inactivity after the root span before finalising a trace |
| `--timeout N` | `300` | Hard timeout (seconds) — force-finalises with `status="partial"` if exceeded |

The collector exposes two endpoints:

- `POST /v1/traces` — OTLP ingest (JSON always; protobuf requires `pip install binex[telemetry]`)
- `GET /health` — returns `{"status": "ok", "pending_traces": N, "finalized_traces": N}`

**How finalisation works:**

1. Spans arrive and are buffered per `traceId`.
2. Once the root span (the span with no parent) has arrived **and** no new spans come in for `--quiet-period` seconds, the trace is finalised and written to the Binex store.
3. If `--timeout` seconds elapse regardless, the trace is force-finalised with `status="partial"`.

This means long-running apps work correctly: Binex waits for the full trace rather than splitting it into multiple partial runs.

## Supported Semantic Conventions

Binex extracts prompt/completion artifacts and cost records from two sets of AI span attributes:

### OpenLLMetry / Traceloop (`gen_ai.*`)

Standard OTLP AI semantic conventions used by Traceloop's SDK and compatible libraries.

| Attribute | Used for |
|-----------|----------|
| `gen_ai.prompt` | Input artifact (`type="prompt"`) |
| `gen_ai.completion` | Output artifact (`type="llm_output"`) |
| `gen_ai.request.model` | Model name for cost calculation |
| `gen_ai.usage.prompt_tokens` | Token count |
| `gen_ai.usage.completion_tokens` | Token count |
| `gen_ai.usage.total_cost` | Explicit cost (takes precedence over token calc) |

### OpenInference (`llm.*`)

Used by LangChain, LlamaIndex, and Arize Phoenix instrumentation.

| Attribute | Used for |
|-----------|----------|
| `llm.input_messages` | Input artifact (`type="prompt"`) |
| `llm.output_messages` | Output artifact (`type="llm_output"`) |
| `llm.model_name` | Model name for cost calculation |
| `llm.token_count.prompt` | Token count |
| `llm.token_count.completion` | Token count |
| `llm.token_count.total_cost` | Explicit cost (takes precedence over token calc) |

When both conventions are present in the same span, **OpenInference takes precedence**.

Plain spans (HTTP calls, DB queries, etc.) produce an `ExecutionRecord` without artifacts — they appear as nodes in the run timeline but have no prompt/completion content.

Cost is computed with a best-effort cascade: explicit attribute → `litellm.completion_cost(model, prompt_tokens, completion_tokens)` → no cost record. Unknown models fall back to `source="llm_tokens_unavailable"`.

## Imported Run Limitations

Runs with `source="otel-import"` have two features disabled:

- **Replay** (`binex replay`, `POST /api/v1/replay`, MCP `replay_node`) — replay requires a native Binex workflow spec. Attempting it returns an error: *"Run was imported from an external trace and cannot be replayed."*
- **Bisect** (`binex bisect`, `POST /api/v1/bisect`) — bisect compares two native runs with matching workflow specs; imported runs are excluded.

Everything else works normally: `binex debug`, `binex trace`, `binex diagnose`, `binex diff`, `binex artifacts`, the web UI RunDetail/Trace/Lineage views, and MCP tools (`debug_node`, `diagnose_run`, `diff_runs`, `get_artifact`).

!!! tip
    To compare an imported run against a native run, use `binex diff <otel-run-id> <native-run-id>`. Diff works across run sources.
