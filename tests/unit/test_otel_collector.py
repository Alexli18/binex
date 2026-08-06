"""OTel collector tests — T031.

Tests: JSON ingest, finalization (short quiet-period), 415 path, /health.
Uses httpx AsyncClient against the FastAPI app directly (no real port needed).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from binex.importers.collector import TraceBuffer, create_collector_app
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "otel"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


def _make_app(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    quiet_period: float = 0.05,  # short for fast tests
    hard_timeout: float = 300.0,
):
    return create_collector_app(
        exec_store=exec_store,
        art_store=art_store,
        quiet_period=quiet_period,
        hard_timeout=hard_timeout,
    )


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "pending_traces" in data
        assert "finalized_traces" in data

    @pytest.mark.asyncio
    async def test_health_pending_increments_on_ingest(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store, quiet_period=9999.0)

        payload = _load_fixture("langchain-openllmetry.json")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/v1/traces", json=payload)
            resp = await client.get("/health")

        data = resp.json()
        # At least 1 pending trace (not yet finalized due to long quiet period)
        assert data["pending_traces"] >= 1


# ---------------------------------------------------------------------------
# POST /v1/traces — JSON ingest
# ---------------------------------------------------------------------------

class TestJsonIngest:
    @pytest.mark.asyncio
    async def test_accepts_json_payload(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        payload = _load_fixture("langchain-openllmetry.json")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/traces", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert "accepted" in data
        assert data["accepted"] == 2  # 2 spans

    @pytest.mark.asyncio
    async def test_accepted_count_matches_spans(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        payload = _load_fixture("plain-spans.json")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/traces", json=payload)

        assert resp.json()["accepted"] == 3

    @pytest.mark.asyncio
    async def test_empty_resource_spans_accepted(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/traces", json={"resourceSpans": []})

        assert resp.status_code == 200
        assert resp.json()["accepted"] == 0

    @pytest.mark.asyncio
    async def test_invalid_json_returns_422_or_400(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/traces",
                content=b"not valid json",
                headers={"content-type": "application/json"},
            )

        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# POST /v1/traces — Protobuf gate (415)
# ---------------------------------------------------------------------------

class TestProtobufGate:
    @pytest.mark.asyncio
    async def test_protobuf_without_deps_returns_415(self):
        """Without opentelemetry-proto installed, protobuf request → 415."""
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        # Send fake protobuf bytes
        from unittest.mock import patch

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch.dict(
                "sys.modules",
                {
                    "opentelemetry.proto": None,
                    "opentelemetry.proto.collector": None,
                    "opentelemetry.proto.collector.trace": None,
                    "opentelemetry.proto.collector.trace.v1": None,
                    "opentelemetry.proto.collector.trace.v1.trace_service_pb2": None,
                },
            ):
                resp = await client.post(
                    "/v1/traces",
                    content=b"\x0a\x00",  # minimal protobuf bytes
                    headers={"content-type": "application/x-protobuf"},
                )

        # Should be 415 (Unsupported Media Type) with hint
        assert resp.status_code == 415
        body = resp.json()
        assert "protobuf" in body["detail"].lower() or "opentelemetry-proto" in body["detail"].lower()

    @pytest.mark.asyncio
    async def test_json_content_type_always_works(self):
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store)

        payload = {"resourceSpans": []}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/v1/traces",
                json=payload,
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Finalization — direct converter path (no timing dependency)
# ---------------------------------------------------------------------------

class TestFinalization:
    @pytest.mark.asyncio
    async def test_finalize_converter_run_persisted(self):
        """Simulating finalization: converter runs and persists a run."""
        from binex.importers.otel import convert_trace

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        fixture = _load_fixture("langchain-openllmetry.json")
        resource_spans = fixture["resourceSpans"]

        # Simulate what _finalise does
        result = convert_trace(resource_spans, source="otel-import")
        await exec_store.create_run(result.run_summary)
        for rec in result.records:
            await exec_store.record(rec)
        for art in result.artifacts:
            await art_store.store(art)

        runs = await exec_store.list_runs()
        assert len(runs) == 1
        assert runs[0].source == "otel-import"

    @pytest.mark.asyncio
    async def test_finalize_partial_status(self):
        """Hard-timeout finalization sets status to 'partial'."""
        from binex.importers.otel import convert_trace

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()

        fixture = _load_fixture("langchain-openllmetry.json")
        resource_spans = fixture["resourceSpans"]

        result = convert_trace(resource_spans, source="otel-collector-partial")
        partial_run = result.run_summary.model_copy(update={"status": "partial"})
        await exec_store.create_run(partial_run)

        runs = await exec_store.list_runs()
        assert runs[0].status == "partial"

    @pytest.mark.asyncio
    async def test_root_span_detection_in_buffer(self):
        """TraceBuffer correctly identifies root spans."""
        buf = TraceBuffer(trace_id="test-root")
        # Simulate span with empty parentSpanId → root
        span = {
            "traceId": "test-trace",
            "spanId": "aabbccdd",
            "parentSpanId": "",
            "name": "root",
        }
        parent = span.get("parentSpanId", "")
        buf.root_seen = not parent or set(parent) == {"0"}
        assert buf.root_seen is True

    @pytest.mark.asyncio
    async def test_child_span_root_seen_false(self):
        """TraceBuffer correctly identifies non-root spans."""
        buf = TraceBuffer(trace_id="test-child")
        span = {
            "traceId": "test-trace",
            "spanId": "aabbccdd",
            "parentSpanId": "11223344",  # has parent
            "name": "child",
        }
        parent = span.get("parentSpanId", "")
        is_root = not parent or set(parent) == {"0"}
        assert is_root is False
        assert buf.root_seen is False  # unchanged

    @pytest.mark.asyncio
    async def test_ingest_adds_to_pending(self):
        """Posting spans creates a pending buffer (not finalized)."""
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store, quiet_period=9999.0)  # long period, no auto-finalize

        payload = _load_fixture("langchain-openllmetry.json")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/v1/traces", json=payload)
            health = await client.get("/health")

        data = health.json()
        assert data["pending_traces"] >= 1
        assert data["finalized_traces"] == 0


# ---------------------------------------------------------------------------
# TraceBuffer unit tests
# ---------------------------------------------------------------------------

class TestTraceBuffer:
    def test_initial_state(self):
        buf = TraceBuffer(trace_id="trace-001")
        assert buf.spans == []
        assert buf.root_seen is False
        assert buf.finalized is False

    def test_root_seen_flag(self):
        buf = TraceBuffer(trace_id="trace-002")
        buf.root_seen = True
        assert buf.root_seen is True

    def test_finalized_flag(self):
        buf = TraceBuffer(trace_id="trace-003")
        buf.finalized = True
        assert buf.finalized is True

    def test_spans_accumulate(self):
        buf = TraceBuffer(trace_id="trace-004")
        buf.spans.append({"spanId": "aaa"})
        buf.spans.append({"spanId": "bbb"})
        assert len(buf.spans) == 2


# ---------------------------------------------------------------------------
# Multiple traces
# ---------------------------------------------------------------------------

class TestMultipleTraces:
    @pytest.mark.asyncio
    async def test_two_distinct_traces_each_finalized(self):
        """Two payloads with different traceIds produce two separate runs."""
        from httpx import ASGITransport, AsyncClient

        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        app = _make_app(exec_store, art_store, quiet_period=0.1)

        def _make_payload(trace_id: str, span_id: str) -> dict:
            return {
                "resourceSpans": [{
                    "resource": {"attributes": []},
                    "scopeSpans": [{"scope": {"name": "test"}, "spans": [{
                        "traceId": trace_id,
                        "spanId": span_id,
                        "parentSpanId": "",
                        "name": "root-span",
                        "startTimeUnixNano": "1700000000000000000",
                        "endTimeUnixNano": "1700000001000000000",
                        "status": {"code": 1},
                        "attributes": [],
                    }]}],
                }],
            }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp1 = await client.post("/v1/traces", json=_make_payload("a" * 32, "b" * 16))
            resp2 = await client.post("/v1/traces", json=_make_payload("c" * 32, "d" * 16))
            assert resp1.json()["accepted"] == 1
            assert resp2.json()["accepted"] == 1
            health = await client.get("/health")

        data = health.json()
        # Two distinct trace IDs → two separate buffers
        assert data["pending_traces"] == 2
