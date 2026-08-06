"""Live OTel collector — receives OTLP/JSON (and optionally protobuf) spans
over HTTP, buffers per-trace, and finalises into Binex stores.

HTTP endpoints:
  POST /v1/traces   — OTLP ingest (JSON always; protobuf if deps available)
  GET  /health      — liveness probe

Finalisation triggers (per trace buffer):
  - Root span received AND quiet period (default 10 s) since last span arrival
  - Hard timeout (default 300 s) regardless — status set to "partial"
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Request, Response  # noqa: F401
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment,misc]
    HTTPException = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    JSONResponse = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-trace in-memory buffer
# ---------------------------------------------------------------------------


@dataclass
class TraceBuffer:
    """Accumulates spans for a single trace until finalisation."""

    trace_id: str
    spans: list[dict[str, Any]] = field(default_factory=list)
    root_seen: bool = False
    resource_attrs: list[dict[str, Any]] = field(default_factory=list)
    scope_name: str = ""
    last_activity: float = field(default_factory=time.monotonic)
    created_at: float = field(default_factory=time.monotonic)
    finalized: bool = False


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------


def create_collector_app(
    exec_store: Any,
    art_store: Any,
    quiet_period: float = 10.0,
    hard_timeout: float = 300.0,
) -> Any:
    """Return a FastAPI app that collects OTLP spans and finalises traces.

    Args:
        exec_store: ExecutionStore instance for persisting runs/records.
        art_store: ArtifactStore instance for persisting artifacts.
        quiet_period: Seconds of inactivity after root span before finalising.
        hard_timeout: Maximum seconds before force-finalising with "partial".
    """
    if FastAPI is None:  # pragma: no cover
        raise ImportError(
            "fastapi is required for the collector. "
            "Install it with: pip install fastapi"
        )

    # In-memory buffer: trace_id → TraceBuffer
    _buffers: dict[str, TraceBuffer] = {}
    _lock = asyncio.Lock()

    # ---------------------------------------------------------------------------
    # Background finaliser task
    # ---------------------------------------------------------------------------

    async def _finalise(trace_id: str, partial: bool = False) -> None:
        """Convert buffered spans and write to stores."""
        async with _lock:
            buf = _buffers.get(trace_id)
            if buf is None or buf.finalized:
                return
            buf.finalized = True
            spans_copy = list(buf.spans)
            resource_attrs = list(buf.resource_attrs)

        if not spans_copy:
            return

        # Build a synthetic resourceSpans structure
        resource_spans = [{
            "resource": {"attributes": resource_attrs},
            "scopeSpans": [{
                "scope": {"name": buf.scope_name},
                "spans": spans_copy,
            }],
        }]

        source = "otel-collector-partial" if partial else "otel-import"

        from binex.importers.otel import convert_trace

        try:
            result = convert_trace(resource_spans, source=source)
            if partial:
                result.run_summary = result.run_summary.model_copy(
                    update={"status": "partial"}
                )
                result.warnings.append("Trace finalised by hard timeout (partial).")

            await exec_store.create_run(result.run_summary)
            for rec in result.records:
                await exec_store.record(rec)
            for art in result.artifacts:
                await art_store.store(art)
            for cost in result.cost_records:
                await exec_store.record_cost(cost)

            total_cost = sum(c.cost for c in result.cost_records)
            if total_cost > 0:
                updated = result.run_summary.model_copy(update={"total_cost": total_cost})
                await exec_store.update_run(updated)

            if result.warnings:
                for w in result.warnings:
                    logger.warning("Collector [%s]: %s", trace_id, w)

            logger.info(
                "Finalised trace %s → run %s (%d nodes, %d artifacts, partial=%s)",
                trace_id, result.run_summary.run_id, len(result.records),
                len(result.artifacts), partial,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Error finalising trace %s", trace_id)

    async def _watch_buffers() -> None:
        """Background coroutine: poll buffers and trigger finalisation."""
        poll_interval = min(1.0, quiet_period / 2) if quiet_period > 0 else 0.05
        while True:
            await asyncio.sleep(poll_interval)
            now = time.monotonic()
            to_finalize: list[tuple[str, bool]] = []

            async with _lock:
                for tid, buf in list(_buffers.items()):
                    if buf.finalized:
                        continue
                    age = now - buf.created_at
                    quiet = now - buf.last_activity

                    if age >= hard_timeout:
                        to_finalize.append((tid, True))
                    elif buf.root_seen and quiet >= quiet_period:
                        to_finalize.append((tid, False))

            for tid, partial in to_finalize:
                await _finalise(tid, partial=partial)

    @asynccontextmanager
    async def _lifespan(app: FastAPI):  # type: ignore[valid-type]
        task = asyncio.create_task(_watch_buffers())
        yield
        task.cancel()

    app = FastAPI(title="Binex OTel Collector", version="1.0.0", lifespan=_lifespan)

    # ---------------------------------------------------------------------------
    # POST /v1/traces
    # ---------------------------------------------------------------------------

    @app.post("/v1/traces")
    async def receive_traces(request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "application/json")

        if "application/x-protobuf" in content_type or "application/grpc" in content_type:
            # Try protobuf
            try:
                from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (  # type: ignore[import]
                    ExportTraceServiceRequest,
                )
                raw = await request.body()
                pb = ExportTraceServiceRequest()
                pb.ParseFromString(raw)
                # Convert protobuf to dict — use json_format
                from google.protobuf import json_format  # type: ignore[import]
                payload = json_format.MessageToDict(pb)
            except ImportError:
                raise HTTPException(
                    status_code=415,
                    detail=(
                        "Protobuf decoding requires 'opentelemetry-proto'. "
                        "Install it with: pip install binex[telemetry] "
                        "or send JSON with Content-Type: application/json"
                    ),
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Protobuf decode error: {exc}")
        else:
            # JSON
            try:
                payload = await request.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"JSON decode error: {exc}")

        resource_spans = payload.get("resourceSpans", [])
        accepted = 0

        async with _lock:
            for rs in resource_spans:
                resource_attrs = rs.get("resource", {}).get("attributes", [])
                for ss in rs.get("scopeSpans", []):
                    scope_name = ss.get("scope", {}).get("name", "")
                    for span in ss.get("spans", []):
                        trace_id = span.get("traceId", "unknown")

                        if trace_id not in _buffers:
                            _buffers[trace_id] = TraceBuffer(
                                trace_id=trace_id,
                                resource_attrs=resource_attrs,
                                scope_name=scope_name,
                            )

                        buf = _buffers[trace_id]
                        if not buf.finalized:
                            buf.spans.append(span)
                            buf.last_activity = time.monotonic()

                            # Check if root span
                            parent = span.get("parentSpanId", "")
                            if not parent or set(parent) == {"0"}:
                                buf.root_seen = True

                            accepted += 1

        return JSONResponse({"accepted": accepted})

    # ---------------------------------------------------------------------------
    # GET /health
    # ---------------------------------------------------------------------------

    @app.get("/health")
    async def health() -> JSONResponse:
        async with _lock:
            pending = sum(1 for b in _buffers.values() if not b.finalized)
            finalized = sum(1 for b in _buffers.values() if b.finalized)
        return JSONResponse({
            "status": "ok",
            "pending_traces": pending,
            "finalized_traces": finalized,
        })

    return app


__all__ = ["TraceBuffer", "create_collector_app"]
