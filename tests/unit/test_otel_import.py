"""Unit tests for OTel importer — T031.

Tests records/artifacts/lineage/cost correctness, warnings, dedup against
``InMemoryExecutionStore`` / ``InMemoryArtifactStore``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from binex.importers.otel import OtelImportResult, convert_trace, import_from_file, parse_otlp_json
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "otel"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


def _resource_spans(name: str) -> list[dict]:
    return _load_fixture(name)["resourceSpans"]


# ---------------------------------------------------------------------------
# parse_otlp_json
# ---------------------------------------------------------------------------

class TestParseOtlpJson:
    def test_parses_string(self):
        data = json.dumps({"resourceSpans": [{"spans": []}]})
        rs = parse_otlp_json(data)
        assert isinstance(rs, list)

    def test_parses_bytes(self):
        data = json.dumps({"resourceSpans": []}).encode()
        rs = parse_otlp_json(data)
        assert rs == []

    def test_parses_dict(self):
        data = {"resourceSpans": [{"foo": "bar"}]}
        rs = parse_otlp_json(data)
        assert rs[0] == {"foo": "bar"}

    def test_missing_key_returns_empty(self):
        rs = parse_otlp_json({})
        assert rs == []


# ---------------------------------------------------------------------------
# RunSummary derivation
# ---------------------------------------------------------------------------

class TestRunSummaryDerivation:
    def test_run_id_prefix(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert result.run_summary.run_id.startswith("otel-")
        assert len(result.run_summary.run_id) == len("otel-") + 12

    def test_source_is_otel_import(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert result.run_summary.source == "otel-import"

    def test_total_nodes_equals_span_count(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert result.run_summary.total_nodes == 2

    def test_completed_nodes(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert result.run_summary.completed_nodes == 2
        assert result.run_summary.failed_nodes == 0

    def test_failed_status_when_error_span(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        assert result.run_summary.status == "failed"
        assert result.run_summary.failed_nodes == 1

    def test_completed_status_all_ok(self):
        rs = _resource_spans("openinference.json")
        result = convert_trace(rs)
        assert result.run_summary.status == "completed"

    def test_workflow_name_from_root_span(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        # Root span name is "chain"
        assert result.run_summary.workflow_name == "chain"

    def test_workflow_name_fallback_service_name(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        # Root span name is "POST /api/chat"
        assert "post" in result.run_summary.workflow_name.lower() or result.run_summary.workflow_name == "my-web-service"

    def test_started_at_earliest_span(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        # Chain started at 1700000000 seconds
        assert result.run_summary.started_at is not None
        assert result.run_summary.started_at.timestamp() == pytest.approx(1700000000.0)

    def test_completed_at_latest_span(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert result.run_summary.completed_at is not None
        assert result.run_summary.completed_at.timestamp() == pytest.approx(1700000003.0)

    def test_empty_spans_warning(self):
        result = convert_trace([])
        assert any("No spans found" in w for w in result.warnings)

    def test_empty_spans_returns_zero_nodes(self):
        result = convert_trace([])
        assert result.run_summary.total_nodes == 0


# ---------------------------------------------------------------------------
# ExecutionRecord fields
# ---------------------------------------------------------------------------

class TestExecutionRecords:
    def test_record_count_equals_span_count(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert len(result.records) == 2

    def test_root_span_has_no_parent_task_id(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        root = next(r for r in result.records if r.task_id == "chain")
        assert root.parent_task_id is None

    def test_child_span_has_parent_task_id(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        child = next(r for r in result.records if r.task_id == "chatopenai")
        assert child.parent_task_id == "chain"

    def test_agent_id_from_scope_name(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        root = next(r for r in result.records if r.task_id == "chain")
        assert root.agent_id == "otel://opentelemetry.instrumentation.langchain"

    def test_latency_ms_computed(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        root = next(r for r in result.records if r.task_id == "chain")
        # 3 seconds = 3000 ms
        assert root.latency_ms == 3000

    def test_trace_id_prefixed(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for rec in result.records:
            assert rec.trace_id.startswith("otel-")

    def test_run_id_on_records(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for rec in result.records:
            assert rec.run_id == result.run_summary.run_id

    def test_failed_span_status(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        failed = next((r for r in result.records if r.status == TaskStatus.FAILED), None)
        assert failed is not None
        assert failed.error == "Downstream timeout"

    def test_completed_span_status(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for rec in result.records:
            assert rec.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Node-ID sanitization and deduplication
# ---------------------------------------------------------------------------

class TestNodeIdSanitization:
    def test_spaces_replaced(self):
        rs = [{
            "resource": {"attributes": []},
            "scopeSpans": [{"scope": {"name": ""}, "spans": [{
                "traceId": "aa" * 16,
                "spanId": "bb" * 8,
                "parentSpanId": "",
                "name": "My Span Name",
                "startTimeUnixNano": "1700000000000000000",
                "endTimeUnixNano": "1700000001000000000",
                "status": {"code": 1},
                "attributes": [],
            }]}],
        }]
        result = convert_trace(rs)
        assert result.records[0].task_id == "my_span_name"

    def test_lowercased(self):
        rs = [{
            "resource": {"attributes": []},
            "scopeSpans": [{"scope": {"name": ""}, "spans": [{
                "traceId": "cc" * 16,
                "spanId": "dd" * 8,
                "parentSpanId": "",
                "name": "ChatOpenAI",
                "startTimeUnixNano": "1700000000000000000",
                "endTimeUnixNano": "1700000001000000000",
                "status": {"code": 1},
                "attributes": [],
            }]}],
        }]
        result = convert_trace(rs)
        assert result.records[0].task_id == "chatopenai"

    def test_deduplication_suffix(self):
        """Two spans with same name get -2 suffix."""
        spans = [
            {
                "traceId": "ee" * 16,
                "spanId": "ff" * 8,
                "parentSpanId": "",
                "name": "ChatOpenAI",
                "startTimeUnixNano": "1700000000000000000",
                "endTimeUnixNano": "1700000001000000000",
                "status": {"code": 1},
                "attributes": [],
            },
            {
                "traceId": "ee" * 16,
                "spanId": "ee" * 8,
                "parentSpanId": "ff" * 8,
                "name": "ChatOpenAI",
                "startTimeUnixNano": "1700000001000000000",
                "endTimeUnixNano": "1700000002000000000",
                "status": {"code": 1},
                "attributes": [],
            },
        ]
        rs = [{"resource": {"attributes": []}, "scopeSpans": [{"scope": {"name": ""}, "spans": spans}]}]
        result = convert_trace(rs)
        task_ids = {r.task_id for r in result.records}
        assert "chatopenai" in task_ids
        assert "chatopenai-2" in task_ids

    def test_empty_name_becomes_span_index(self):
        rs = [{
            "resource": {"attributes": []},
            "scopeSpans": [{"scope": {"name": ""}, "spans": [{
                "traceId": "11" * 16,
                "spanId": "22" * 8,
                "parentSpanId": "",
                "name": "!!!/###",
                "startTimeUnixNano": "1700000000000000000",
                "endTimeUnixNano": "1700000001000000000",
                "status": {"code": 1},
                "attributes": [],
            }]}],
        }]
        result = convert_trace(rs)
        # After sanitization: only _ and empty -> span_0
        assert result.records[0].task_id.startswith("span_")

    def test_truncated_to_64(self):
        long_name = "a" * 100
        rs = [{
            "resource": {"attributes": []},
            "scopeSpans": [{"scope": {"name": ""}, "spans": [{
                "traceId": "33" * 16,
                "spanId": "44" * 8,
                "parentSpanId": "",
                "name": long_name,
                "startTimeUnixNano": "1700000000000000000",
                "endTimeUnixNano": "1700000001000000000",
                "status": {"code": 1},
                "attributes": [],
            }]}],
        }]
        result = convert_trace(rs)
        assert len(result.records[0].task_id) <= 64


# ---------------------------------------------------------------------------
# Artifacts from LLM semconv — OpenLLMetry (gen_ai.*)
# ---------------------------------------------------------------------------

class TestOpenLLMetryArtifacts:
    def test_input_artifact_created(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        input_arts = [a for a in result.artifacts if a.type == "prompt"]
        assert len(input_arts) >= 1

    def test_output_artifact_created(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        output_arts = [a for a in result.artifacts if a.type == "llm_output"]
        assert len(output_arts) >= 1

    def test_artifact_run_id(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for art in result.artifacts:
            assert art.run_id == result.run_summary.run_id

    def test_artifact_produced_by(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for art in result.artifacts:
            assert art.lineage.produced_by in {r.task_id for r in result.records}

    def test_input_artifact_id_format(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        input_arts = [a for a in result.artifacts if a.type == "prompt"]
        for art in input_arts:
            assert art.id.endswith("_input")

    def test_output_artifact_id_format(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        output_arts = [a for a in result.artifacts if a.type == "llm_output"]
        for art in output_arts:
            assert art.id.endswith("_output")

    def test_prompt_content_matches_gen_ai_prompt(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        chain_input = next(a for a in result.artifacts if a.id == "chain_input")
        assert "artificial intelligence" in str(chain_input.content).lower()

    def test_output_content_matches_gen_ai_completion(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        chain_output = next(a for a in result.artifacts if a.id == "chain_output")
        assert "artificial intelligence" in str(chain_output.content).lower()


# ---------------------------------------------------------------------------
# Artifacts — OpenInference (llm.*)
# ---------------------------------------------------------------------------

class TestOpenInferenceArtifacts:
    def test_input_artifact_created(self):
        rs = _resource_spans("openinference.json")
        result = convert_trace(rs)
        input_arts = [a for a in result.artifacts if a.type == "prompt"]
        assert len(input_arts) >= 1

    def test_output_artifact_created(self):
        rs = _resource_spans("openinference.json")
        result = convert_trace(rs)
        output_arts = [a for a in result.artifacts if a.type == "llm_output"]
        assert len(output_arts) >= 1

    def test_input_content_is_parsed_json_array(self):
        rs = _resource_spans("openinference.json")
        result = convert_trace(rs)
        root_input = next((a for a in result.artifacts if a.id == "retrievalqa_input"), None)
        assert root_input is not None
        assert isinstance(root_input.content, list)

    def test_output_content_is_parsed_json_array(self):
        rs = _resource_spans("openinference.json")
        result = convert_trace(rs)
        root_output = next((a for a in result.artifacts if a.id == "retrievalqa_output"), None)
        assert root_output is not None
        assert isinstance(root_output.content, list)


# ---------------------------------------------------------------------------
# Plain spans — no AI artifacts
# ---------------------------------------------------------------------------

class TestPlainSpans:
    def test_no_artifacts_for_plain_spans(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        assert len(result.artifacts) == 0

    def test_records_created_for_plain_spans(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        assert len(result.records) == 3

    def test_no_cost_records_for_plain_spans(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        assert len(result.cost_records) == 0


# ---------------------------------------------------------------------------
# Lineage chain
# ---------------------------------------------------------------------------

class TestLineage:
    def test_child_output_derived_from_parent_output(self):
        """Child's input artifact's derived_from should include parent output."""
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        # chain_output (parent) → chatopenai_input (child) derived_from chain_output
        child_input = next((a for a in result.artifacts if a.id == "chatopenai_input"), None)
        if child_input:  # only if child has input art
            assert "chain_output" in child_input.lineage.derived_from

    def test_root_artifact_has_no_derived_from(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        root_input = next((a for a in result.artifacts if a.id == "chain_input"), None)
        if root_input:
            assert root_input.lineage.derived_from == []


# ---------------------------------------------------------------------------
# Cost records
# ---------------------------------------------------------------------------

class TestCostRecords:
    def test_cost_records_created_for_ai_spans(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        assert len(result.cost_records) >= 1

    def test_cost_record_has_model(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for cr in result.cost_records:
            assert cr.model is not None

    def test_cost_record_model_matches_gen_ai_request_model(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        chain_cost = next((c for c in result.cost_records if c.task_id == "chain"), None)
        assert chain_cost is not None
        assert chain_cost.model == "gpt-4o"

    def test_cost_record_token_counts(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        chain_cost = next((c for c in result.cost_records if c.task_id == "chain"), None)
        assert chain_cost is not None
        assert chain_cost.prompt_tokens == 12
        assert chain_cost.completion_tokens == 18

    def test_cost_record_run_id(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for cr in result.cost_records:
            assert cr.run_id == result.run_summary.run_id

    def test_cost_source_is_otel_import_or_unavailable(self):
        rs = _resource_spans("langchain-openllmetry.json")
        result = convert_trace(rs)
        for cr in result.cost_records:
            assert cr.source in ("otel-import", "llm_tokens_unavailable")

    def test_openinference_cost_tokens(self):
        rs = _resource_spans("openinference.json")
        result = convert_trace(rs)
        root_cost = next((c for c in result.cost_records if c.task_id == "retrievalqa"), None)
        assert root_cost is not None
        assert root_cost.prompt_tokens == 10
        assert root_cost.completion_tokens == 9
        assert root_cost.model == "gpt-4o-mini"

    def test_no_cost_records_for_plain_spans(self):
        rs = _resource_spans("plain-spans.json")
        result = convert_trace(rs)
        assert len(result.cost_records) == 0


# ---------------------------------------------------------------------------
# Orphan spans
# ---------------------------------------------------------------------------

class TestOrphanSpans:
    def test_orphan_warning_emitted(self):
        rs = _resource_spans("orphan-spans.json")
        result = convert_trace(rs)
        assert any("orphan" in w.lower() for w in result.warnings)

    def test_orphan_spans_become_roots(self):
        rs = _resource_spans("orphan-spans.json")
        result = convert_trace(rs)
        # orphaned.embedding has nonexistent parent → should become root
        orphan_rec = next(
            (r for r in result.records if "orphaned" in r.task_id),
            None,
        )
        assert orphan_rec is not None
        assert orphan_rec.parent_task_id is None

    def test_non_orphan_spans_preserve_parent(self):
        """token.counter has valid parent openai.chat.completions."""
        rs = _resource_spans("orphan-spans.json")
        result = convert_trace(rs)
        token_rec = next((r for r in result.records if "token" in r.task_id), None)
        assert token_rec is not None
        # Parent should be the openai.chat.completions span
        assert token_rec.parent_task_id is not None

    def test_all_records_present(self):
        rs = _resource_spans("orphan-spans.json")
        result = convert_trace(rs)
        assert len(result.records) == 3


# ---------------------------------------------------------------------------
# import_from_file — persistence
# ---------------------------------------------------------------------------

class TestImportFromFile:
    @pytest.mark.asyncio
    async def test_run_persisted(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        fixture_path = str(FIXTURES / "langchain-openllmetry.json")
        result = await import_from_file(fixture_path, exec_store, art_store)
        run = await exec_store.get_run(result.run_summary.run_id)
        assert run is not None
        assert run.source == "otel-import"

    @pytest.mark.asyncio
    async def test_records_persisted(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        fixture_path = str(FIXTURES / "langchain-openllmetry.json")
        result = await import_from_file(fixture_path, exec_store, art_store)
        records = await exec_store.list_records(result.run_summary.run_id)
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_artifacts_persisted(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        fixture_path = str(FIXTURES / "langchain-openllmetry.json")
        result = await import_from_file(fixture_path, exec_store, art_store)
        arts = await art_store.list_by_run(result.run_summary.run_id)
        assert len(arts) == len(result.artifacts)

    @pytest.mark.asyncio
    async def test_cost_records_persisted(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        fixture_path = str(FIXTURES / "langchain-openllmetry.json")
        result = await import_from_file(fixture_path, exec_store, art_store)
        costs = await exec_store.list_costs(result.run_summary.run_id)
        assert len(costs) == len(result.cost_records)

    @pytest.mark.asyncio
    async def test_plain_spans_no_artifacts(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        fixture_path = str(FIXTURES / "plain-spans.json")
        result = await import_from_file(fixture_path, exec_store, art_store)
        arts = await art_store.list_by_run(result.run_summary.run_id)
        assert len(arts) == 0

    @pytest.mark.asyncio
    async def test_orphan_spans_file(self):
        exec_store = InMemoryExecutionStore()
        art_store = InMemoryArtifactStore()
        fixture_path = str(FIXTURES / "orphan-spans.json")
        result = await import_from_file(fixture_path, exec_store, art_store)
        assert any("orphan" in w.lower() for w in result.warnings)
        run = await exec_store.get_run(result.run_summary.run_id)
        assert run is not None
