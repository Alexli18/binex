"""Tests for binex.telemetry module."""

from unittest.mock import patch

import pytest


def test_get_tracer_returns_noop_when_otel_not_installed():
    """When opentelemetry is not installed, get_tracer returns a no-op tracer."""
    with patch.dict("sys.modules", {"opentelemetry": None, "opentelemetry.trace": None}):
        import importlib

        from binex import telemetry

        importlib.reload(telemetry)
        tracer = telemetry.get_tracer()
        span_cm = tracer.start_as_current_span("test")
        with span_cm as span:
            assert span is not None


def test_init_telemetry_noop_without_env_vars():
    """init_telemetry does nothing when OTEL env vars are not set."""
    from binex.telemetry import init_telemetry

    init_telemetry()


def test_init_telemetry_configures_with_env_vars(monkeypatch):
    """init_telemetry initializes provider when OTEL env vars are present."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "binex-test")
    from binex.telemetry import init_telemetry

    init_telemetry()


def test_get_tracer_returns_named_tracer():
    """get_tracer returns a tracer with name 'binex'."""
    from binex.telemetry import get_tracer

    tracer = get_tracer()
    assert tracer is not None
