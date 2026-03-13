# Telemetry

## Overview

Binex supports optional OpenTelemetry (OTEL) tracing for workflow execution. When enabled, it emits run-level and node-level spans to external collectors like Jaeger, Tempo, or any OTLP-compatible backend.

**Design principle:** Zero overhead when disabled. If OpenTelemetry is not installed or no environment variables are set, a no-op tracer is used — no conditional branching in business logic.

## Architecture

```
src/binex/telemetry.py
    |
    |--- init_telemetry()     Called once at CLI startup
    |--- get_tracer()         Returns OTEL tracer or _NoOpTracer
    |
    |--- _NoOpTracer          Context manager stub (when OTEL unavailable)
    |--- _NoOpSpan            Attribute/exception sink (does nothing)
```

### Span hierarchy

```
binex.run (parent)
├── binex.node.planner (child)
├── binex.node.researcher (child)    # parallel nodes have overlapping timestamps
├── binex.node.researcher2 (child)
└── binex.node.summarizer (child)
```

### Span attributes

**Run-level span** (`binex.run`):

| Attribute | Type | Source |
|-----------|------|--------|
| `workflow.name` | string | `WorkflowSpec.name` |
| `run.id` | string | `RunSummary.run_id` |
| `run.status` | string | `RunSummary.status` |
| `run.total_cost` | float | `RunSummary.total_cost` |
| `run.node_count` | int | `RunSummary.total_nodes` |

**Node-level span** (`binex.node.{node_id}`):

| Attribute | Type | Source |
|-----------|------|--------|
| `node.id` | string | `TaskNode.node_id` |
| `node.agent` | string | `TaskNode.agent` |
| `node.status` | string | `"completed"` or `"failed"` |

Exceptions are recorded on the span via `span.record_exception()` when a node fails.

## Installation

```bash
pip install binex[telemetry]
```

This installs:

- `opentelemetry-api >= 1.20`
- `opentelemetry-sdk >= 1.20`
- `opentelemetry-exporter-otlp >= 1.20`

## Configuration

Tracing is controlled entirely via standard OTEL environment variables — no CLI flags or config files needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(none)* | Collector endpoint (e.g., `http://localhost:4317`). If unset, tracing is disabled. |
| `OTEL_SERVICE_NAME` | `"binex"` | Service name in traces |
| `OTEL_TRACES_EXPORTER` | `"otlp"` | Exporter type |

**Activation rule:** Tracing activates only when `opentelemetry` is installed AND at least one of `OTEL_EXPORTER_OTLP_ENDPOINT` or `OTEL_TRACES_EXPORTER` is set.

## Usage

```bash
# Set up collector
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=binex

# Run a workflow — spans are automatically emitted
binex run examples/simple.yaml
```

Then open your collector UI (Jaeger, Grafana Tempo, etc.) and search for service `binex`.

## No-op fallback

When OTEL is not available, `get_tracer()` returns a `_NoOpTracer` that implements the same context manager interface:

```python
class _NoOpSpan:
    def set_attribute(self, key, value): pass
    def record_exception(self, exception): pass

class _NoOpTracer:
    def start_as_current_span(self, name, **kwargs):
        yield _NoOpSpan()
```

This means instrumented code always calls the same API — no `if tracer:` checks needed.

## Collector unavailability

The OTEL SDK's `BatchSpanProcessor` silently drops spans if the collector is unreachable. No custom error handling is needed — runs complete normally regardless of collector status.
