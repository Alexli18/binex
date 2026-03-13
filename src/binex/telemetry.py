"""Optional OpenTelemetry integration — no-op when not installed or not configured."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

_HAS_OTEL = False
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _HAS_OTEL = True
except ImportError:
    pass

_initialized = False


class _NoOpSpan:
    """Minimal no-op span for when OTEL is unavailable."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """Minimal no-op tracer for when OTEL is unavailable."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield _NoOpSpan()


def init_telemetry() -> None:
    """Initialize OTEL tracing if the SDK is installed and env vars are set.

    Checks for OTEL_EXPORTER_OTLP_ENDPOINT or OTEL_TRACES_EXPORTER.
    If neither is set, tracing stays disabled (no-op).
    """
    global _initialized

    if _initialized:
        return

    if not _HAS_OTEL:
        logger.debug("opentelemetry not installed — tracing disabled")
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    exporter_name = os.environ.get("OTEL_TRACES_EXPORTER")

    if not endpoint and not exporter_name:
        logger.debug("No OTEL env vars set — tracing disabled")
        return

    service_name = os.environ.get("OTEL_SERVICE_NAME", "binex")
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except ImportError:
        logger.warning(
            "OTLP exporter not available — install opentelemetry-exporter-otlp"
        )
        return

    trace.set_tracer_provider(provider)
    _initialized = True
    logger.info("OpenTelemetry tracing initialized (endpoint=%s)", endpoint)


def get_tracer() -> Any:
    """Return an OTEL tracer or a no-op stub."""
    if _HAS_OTEL:
        return trace.get_tracer("binex")
    return _NoOpTracer()
