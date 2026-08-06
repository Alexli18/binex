"""OTel → Binex converter.

Parses an OTLP/JSON ``ExportTraceServiceRequest`` and produces:
- One ``RunSummary`` per trace (``source="otel-import"``)
- One ``ExecutionRecord`` per span
- Optional ``Artifact``s (prompt/output) for AI-instrumented spans
- Optional ``CostRecord``s from token counts

Supported semantic conventions:
- OpenInference (``llm.*``) — LangChain / LlamaIndex / Arize
- OpenLLMetry / Traceloop (``gen_ai.*``) — standard OTLP AI semconv

No new runtime dependencies — uses ``json`` (stdlib) only.
``litellm.completion_cost`` is imported lazily and degrades gracefully.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore

# ---------------------------------------------------------------------------
# OTLP helpers
# ---------------------------------------------------------------------------

def _get_attr(attributes: list[dict[str, Any]], key: str) -> Any:
    """Extract a scalar value from OTLP attribute list by key."""
    for attr in attributes:
        if attr.get("key") == key:
            val = attr.get("value", {})
            if isinstance(val, dict):
                for vtype in ("stringValue", "intValue", "doubleValue", "boolValue"):
                    if vtype in val:
                        v = val[vtype]
                        # intValue may be a string in JSON encoding
                        if vtype == "intValue" and isinstance(v, str):
                            return int(v)
                        return v
            return val
    return None


def _ns_to_datetime(ns: Any) -> datetime:
    """Convert Unix nanoseconds (int or string) to UTC datetime."""
    ns_int = int(ns) if ns is not None else 0
    return datetime.fromtimestamp(ns_int / 1_000_000_000, tz=UTC)


def _ns_to_ms(start_ns: Any, end_ns: Any) -> int:
    """Return elapsed milliseconds between two nanosecond timestamps."""
    return max(0, int((int(end_ns) - int(start_ns)) / 1_000_000))


def _is_root_span(span: dict[str, Any]) -> bool:
    """Return True if this span has no valid parent."""
    parent = span.get("parentSpanId", "")
    return not parent or parent == "0" * len(parent) or set(parent) == {"0"}


_SANITIZE_RE = re.compile(r"[^a-z0-9_\-]+")


def _sanitize_node_id(name: str, index: int = 0) -> str:
    """Convert a span name to a valid node-id string."""
    s = name.lower()
    s = _SANITIZE_RE.sub("_", s)
    s = s.strip("_")
    s = s[:64]
    if not s:
        s = f"span_{index}"
    return s


# ---------------------------------------------------------------------------
# Data container for a trace being processed
# ---------------------------------------------------------------------------

@dataclass
class _SpanInfo:
    raw: dict[str, Any]
    span_id: str
    parent_span_id: str | None
    task_id: str          # sanitized, deduplicated
    attrs: list[dict[str, Any]] = field(default_factory=list)
    scope_name: str = ""
    start_ns: int = 0
    end_ns: int = 0


# ---------------------------------------------------------------------------
# OTel converter result
# ---------------------------------------------------------------------------

@dataclass
class OtelImportResult:
    """Result of converting a single OTLP trace."""

    run_summary: RunSummary
    records: list[ExecutionRecord]
    artifacts: list[Artifact]
    cost_records: list[CostRecord]
    warnings: list[str]


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

def convert_trace(
    resource_spans: list[dict[str, Any]],
    *,
    source: str = "otel-import",
) -> OtelImportResult:
    """Convert a list of ``resourceSpans`` into Binex domain objects.

    Args:
        resource_spans: The ``resourceSpans`` array from an OTLP JSON export.
        source: The source tag to attach to the ``RunSummary``.

    Returns:
        An ``OtelImportResult`` containing all produced domain objects plus
        any non-fatal warning messages.
    """
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # 1. Flatten all spans, collecting resource attributes per span
    # ------------------------------------------------------------------
    all_raw_spans: list[dict[str, Any]] = []
    all_resource_attrs: list[list[dict[str, Any]]] = []
    all_scope_names: list[str] = []

    for rs in resource_spans:
        resource_attrs: list[dict[str, Any]] = rs.get("resource", {}).get("attributes", [])
        for ss in rs.get("scopeSpans", []):
            scope_name: str = ss.get("scope", {}).get("name", "")
            for span in ss.get("spans", []):
                all_raw_spans.append(span)
                all_resource_attrs.append(resource_attrs)
                all_scope_names.append(scope_name)

    if not all_raw_spans:
        warnings.append("No spans found in trace — skipped.")
        # Return a placeholder
        run_id = "otel-" + uuid.uuid4().hex[:12]
        dummy = RunSummary(
            run_id=run_id,
            workflow_name="unknown",
            status="completed",
            total_nodes=0,
            source=source,
        )
        return OtelImportResult(
            run_summary=dummy,
            records=[],
            artifacts=[],
            cost_records=[],
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # 2. Determine traceId (use first span's — all should match)
    # ------------------------------------------------------------------
    trace_id = all_raw_spans[0].get("traceId", uuid.uuid4().hex)
    run_id = "otel-" + trace_id[:12]

    # ------------------------------------------------------------------
    # 3. Build span_id → task_id map (first pass — sanitize + dedup)
    # ------------------------------------------------------------------
    span_id_to_info: dict[str, _SpanInfo] = {}
    name_counts: dict[str, int] = {}  # sanitized name → occurrence count

    for idx, (raw, resource_attrs, scope_name) in enumerate(
        zip(all_raw_spans, all_resource_attrs, all_scope_names)
    ):
        span_id = raw.get("spanId", f"span_{idx}")
        parent_span_id = raw.get("parentSpanId") or None
        if parent_span_id and (set(parent_span_id) == {"0"} or not parent_span_id.strip("0")):
            parent_span_id = None

        raw_name = raw.get("name", f"span_{idx}")
        base_id = _sanitize_node_id(raw_name, idx)

        # Dedup
        count = name_counts.get(base_id, 0) + 1
        name_counts[base_id] = count
        task_id = base_id if count == 1 else f"{base_id}-{count}"

        attrs: list[dict[str, Any]] = raw.get("attributes", [])
        start_ns = int(raw.get("startTimeUnixNano", 0))
        end_ns = int(raw.get("endTimeUnixNano", 0))

        info = _SpanInfo(
            raw=raw,
            span_id=span_id,
            parent_span_id=parent_span_id,
            task_id=task_id,
            attrs=attrs,
            scope_name=scope_name,
            start_ns=start_ns,
            end_ns=end_ns,
        )
        span_id_to_info[span_id] = info

    # ------------------------------------------------------------------
    # 4. Resolve parent task_ids from parent span_ids
    # ------------------------------------------------------------------
    span_id_to_task_id = {sid: info.task_id for sid, info in span_id_to_info.items()}

    # ------------------------------------------------------------------
    # 5. Identify roots and orphans
    # ------------------------------------------------------------------
    root_infos: list[_SpanInfo] = []
    orphan_infos: list[_SpanInfo] = []

    for info in span_id_to_info.values():
        if info.parent_span_id is None:
            root_infos.append(info)
        elif info.parent_span_id not in span_id_to_info:
            orphan_infos.append(info)

    if not root_infos:
        # Promote orphans to roots
        root_infos = orphan_infos[:]
        orphan_infos = []
        warnings.append(f"No root spans found — all {len(root_infos)} spans treated as roots.")

    if len(root_infos) > 1:
        warnings.append(
            "Multiple root spans detected: "
            + str([i.task_id for i in sorted(root_infos, key=lambda x: x.start_ns)])
        )

    if orphan_infos:
        orphan_task_ids = [i.task_id for i in orphan_infos]
        warnings.append(f"Orphan spans attached as roots: {orphan_task_ids}")
        # Orphans become roots in the flat span list
        for oi in orphan_infos:
            oi.parent_span_id = None

    # ------------------------------------------------------------------
    # 6. Determine RunSummary fields
    # ------------------------------------------------------------------
    # workflow_name: first root span name (by start_ns) or service.name
    sorted_roots = sorted(root_infos, key=lambda i: i.start_ns)
    workflow_name = "unknown"
    if sorted_roots:
        workflow_name = sorted_roots[0].raw.get("name", "unknown")
    # service.name from first resource
    if all_resource_attrs and not workflow_name:
        svc = _get_attr(all_resource_attrs[0], "service.name")
        if svc:
            workflow_name = str(svc)

    # service.name fallback if root name is still "unknown"
    if workflow_name == "unknown" and all_resource_attrs:
        svc = _get_attr(all_resource_attrs[0], "service.name")
        if svc:
            workflow_name = str(svc)

    all_infos = list(span_id_to_info.values())
    min_start = min((i.start_ns for i in all_infos), default=0)
    max_end = max((i.end_ns for i in all_infos), default=0)

    # Status: "failed" if any ERROR span, else "completed"
    status_code_error = 2
    has_error = any(
        info.raw.get("status", {}).get("code") == status_code_error
        for info in all_infos
    )
    run_status = "failed" if has_error else "completed"

    failed_count = sum(
        1 for info in all_infos
        if info.raw.get("status", {}).get("code") == status_code_error
    )
    completed_count = len(all_infos) - failed_count

    run_summary = RunSummary(
        run_id=run_id,
        workflow_name=workflow_name,
        status=run_status,
        started_at=_ns_to_datetime(min_start),
        completed_at=_ns_to_datetime(max_end),
        total_nodes=len(all_infos),
        completed_nodes=completed_count,
        failed_nodes=failed_count,
        source=source,
    )

    # ------------------------------------------------------------------
    # 7. Build ExecutionRecord + Artifacts + CostRecords per span
    # ------------------------------------------------------------------
    records: list[ExecutionRecord] = []
    artifacts: list[Artifact] = []
    cost_records: list[CostRecord] = []

    # Track which task_ids have output artifacts (for lineage derivation)
    task_id_has_output: set[str] = set()

    # We need two passes: first collect which spans produce output (for lineage)
    # This is handled inline — we track as we go and lineage is set via derived_from
    # pointing to parent's output artifact.

    # Sort spans by start time for deterministic ordering
    sorted_infos = sorted(all_infos, key=lambda i: i.start_ns)

    for info in sorted_infos:
        span = info.raw
        task_id = info.task_id
        span_id = info.span_id
        attrs = info.attrs

        # parent_task_id
        parent_task_id: str | None = None
        if info.parent_span_id and info.parent_span_id in span_id_to_task_id:
            parent_task_id = span_id_to_task_id[info.parent_span_id]

        # agent_id
        agent_id = f"otel://{info.scope_name}" if info.scope_name else "otel://unknown"

        # status
        status_code = span.get("status", {}).get("code", 1)
        status_code_error = 2
        if status_code == status_code_error:
            rec_status = TaskStatus.FAILED
            rec_error: str | None = span.get("status", {}).get("message") or "Error"
        else:
            rec_status = TaskStatus.COMPLETED
            rec_error = None

        # latency
        latency_ms = _ns_to_ms(info.start_ns, info.end_ns)
        timestamp = _ns_to_datetime(info.start_ns)

        # Artifacts from LLM semconv
        input_art: Artifact | None = None
        output_art: Artifact | None = None
        model_name: str | None = None
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        explicit_cost: float | None = None

        # Check OpenInference first (higher precedence)
        oi_input = _get_attr(attrs, "llm.input_messages")
        oi_output = _get_attr(attrs, "llm.output_messages")
        oi_model = _get_attr(attrs, "llm.model_name")
        oi_prompt_tok = _get_attr(attrs, "llm.token_count.prompt")
        oi_compl_tok = _get_attr(attrs, "llm.token_count.completion")
        oi_total_cost = _get_attr(attrs, "llm.token_count.total_cost")

        # OpenLLMetry / gen_ai semconv
        ga_prompt = _get_attr(attrs, "gen_ai.prompt")
        ga_completion = _get_attr(attrs, "gen_ai.completion")
        ga_model = _get_attr(attrs, "gen_ai.request.model")
        ga_prompt_tok = _get_attr(attrs, "gen_ai.usage.prompt_tokens")
        ga_compl_tok = _get_attr(attrs, "gen_ai.usage.completion_tokens")
        ga_total_cost = _get_attr(attrs, "gen_ai.usage.total_cost")

        has_ai_semconv = any([
            oi_input, oi_output, oi_model, oi_prompt_tok, oi_compl_tok,
            ga_prompt, ga_completion, ga_model, ga_prompt_tok, ga_compl_tok,
        ])

        if not has_ai_semconv:
            # Check if there are any llm.* or gen_ai.* at all
            all_keys = {a.get("key", "") for a in attrs}
            if not any(k.startswith("llm.") or k.startswith("gen_ai.") for k in all_keys):
                pass  # plain span — no artifacts
            else:
                has_ai_semconv = True  # partial semconv

        if has_ai_semconv:
            # Resolve using OpenInference first, gen_ai fallback
            input_content: Any = None
            output_content: Any = None

            if oi_input is not None:
                # May be JSON array or string
                input_content = _parse_json_or_str(oi_input)
                model_name = str(oi_model) if oi_model is not None else None
                prompt_tokens = int(oi_prompt_tok) if oi_prompt_tok is not None else None
                completion_tokens = int(oi_compl_tok) if oi_compl_tok is not None else None
                explicit_cost = float(oi_total_cost) if oi_total_cost is not None else None
            elif ga_prompt is not None:
                input_content = _parse_json_or_str(ga_prompt)

            if oi_output is not None:
                output_content = _parse_json_or_str(oi_output)
            elif ga_completion is not None:
                output_content = _parse_json_or_str(ga_completion)

            if ga_model is not None and model_name is None:
                model_name = str(ga_model)
            if ga_prompt_tok is not None and prompt_tokens is None:
                prompt_tokens = int(ga_prompt_tok)
            if ga_compl_tok is not None and completion_tokens is None:
                completion_tokens = int(ga_compl_tok)
            if ga_total_cost is not None and explicit_cost is None:
                explicit_cost = float(ga_total_cost)

            # Lineage: derived_from parent's output artifact (if parent had one)
            derived_from: list[str] = []
            if parent_task_id and parent_task_id in task_id_has_output:
                derived_from = [f"{parent_task_id}_output"]

            if input_content is not None:
                input_art = Artifact(
                    id=f"{task_id}_input",
                    run_id=run_id,
                    type="prompt",
                    content=input_content,
                    lineage=Lineage(
                        produced_by=task_id,
                        derived_from=derived_from,
                    ),
                )

            if output_content is not None:
                output_art = Artifact(
                    id=f"{task_id}_output",
                    run_id=run_id,
                    type="llm_output",
                    content=output_content,
                    lineage=Lineage(
                        produced_by=task_id,
                        derived_from=[f"{task_id}_input"] if input_art else derived_from,
                    ),
                )
                task_id_has_output.add(task_id)

        input_refs: list[str] = [input_art.id] if input_art else []
        output_refs: list[str] = [output_art.id] if output_art else []

        record = ExecutionRecord(
            id=f"{run_id}-{task_id}",
            run_id=run_id,
            task_id=task_id,
            parent_task_id=parent_task_id,
            agent_id=agent_id,
            status=rec_status,
            input_artifact_refs=input_refs,
            output_artifact_refs=output_refs,
            latency_ms=latency_ms,
            timestamp=timestamp,
            trace_id=f"otel-{trace_id}",
            error=rec_error,
        )
        records.append(record)
        if input_art:
            artifacts.append(input_art)
        if output_art:
            artifacts.append(output_art)

        # Cost record
        has_cost_data = (
            explicit_cost is not None or prompt_tokens is not None or model_name is not None
        )
        if has_ai_semconv and has_cost_data:
            cost_val: float = 0.0
            cost_source = "otel-import"

            if explicit_cost is not None:
                cost_val = explicit_cost
            elif prompt_tokens is not None and model_name is not None:
                try:
                    import litellm  # type: ignore[import-untyped]
                    cost_val = litellm.completion_cost(
                        model=model_name,
                        prompt_tokens=prompt_tokens or 0,
                        completion_tokens=completion_tokens or 0,
                    )
                except Exception:  # noqa: BLE001
                    cost_source = "llm_tokens_unavailable"
            else:
                cost_source = "llm_tokens_unavailable"

            cost_record = CostRecord(
                id=f"{run_id}-cost-{task_id}",
                run_id=run_id,
                task_id=task_id,
                model=model_name,
                cost=cost_val,
                source=cost_source,  # type: ignore[arg-type]
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            cost_records.append(cost_record)

    return OtelImportResult(
        run_summary=run_summary,
        records=records,
        artifacts=artifacts,
        cost_records=cost_records,
        warnings=warnings,
    )


def _parse_json_or_str(value: Any) -> Any:
    """Try to parse value as JSON; return raw string if not parseable."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
    return value


# ---------------------------------------------------------------------------
# File-based import: parse OTLP JSON file → convert → write to stores
# ---------------------------------------------------------------------------

def parse_otlp_json(data: str | bytes | dict[str, Any]) -> list[dict[str, Any]]:
    """Parse raw OTLP JSON and return the ``resourceSpans`` list."""
    if isinstance(data, (str, bytes)):
        payload = json.loads(data)
    else:
        payload = data
    return payload.get("resourceSpans", [])


async def import_from_file(
    file_path: str,
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
) -> OtelImportResult:
    """Read an OTLP/JSON file, convert, and persist to stores.

    Returns an ``OtelImportResult`` with the produced objects and any warnings.
    """
    with open(file_path, encoding="utf-8") as fh:
        raw = fh.read()

    resource_spans = parse_otlp_json(raw)

    # Group by traceId — one RunSummary per trace
    trace_buckets: dict[str, list[dict[str, Any]]] = {}
    for rs in resource_spans:
        for ss in rs.get("scopeSpans", []):
            for span in ss.get("spans", []):
                tid = span.get("traceId", "unknown")
                if tid not in trace_buckets:
                    trace_buckets[tid] = []
                trace_buckets[tid].append(None)  # just count

    # Re-bucket by traceId at the resourceSpans level
    # For simplicity, treat the whole file as one trace (most common case)
    result = convert_trace(resource_spans)

    await exec_store.create_run(result.run_summary)
    for rec in result.records:
        await exec_store.record(rec)
    for art in result.artifacts:
        await art_store.store(art)
    for cost in result.cost_records:
        await exec_store.record_cost(cost)

    # Update run total_cost
    total_cost = sum(c.cost for c in result.cost_records)
    if total_cost > 0:
        updated = result.run_summary.model_copy(update={"total_cost": total_cost})
        await exec_store.update_run(updated)
        result.run_summary = updated

    return result


__all__ = [
    "OtelImportResult",
    "convert_trace",
    "import_from_file",
    "parse_otlp_json",
]
