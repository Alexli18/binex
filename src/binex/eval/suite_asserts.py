"""Assert engine — evaluate asserts against run artifacts."""

from __future__ import annotations

import json
from typing import Any

from binex.eval import checks
from binex.eval.models import AssertResult, EvalAssert, EvalCase
from binex.stores.artifact_store import ArtifactStore
from binex.stores.execution_store import ExecutionStore


async def evaluate_asserts(
    case: EvalCase,
    run_id: str,
    exec_store: ExecutionStore,
    art_store: ArtifactStore,
) -> list[AssertResult]:
    """Evaluate all asserts for a case against the run's artifacts."""
    records = await exec_store.list_records(run_id)
    record_by_node = {r.task_id: r for r in records}

    terminal_nodes = _find_terminal_nodes(records)

    results: list[AssertResult] = []
    for idx, assert_def in enumerate(case.asserts):
        result = await _evaluate_one(
            idx, assert_def, run_id, record_by_node, terminal_nodes, art_store
        )
        results.append(result)
    return results


def _find_terminal_nodes(records: list) -> list[str]:
    """Nodes that are not a parent of any other node."""
    all_ids = {r.task_id for r in records}
    parent_ids = {r.parent_task_id for r in records if r.parent_task_id}
    terminals = all_ids - parent_ids
    return list(terminals) if terminals else list(all_ids)


async def _get_content_for_node(
    node_id: str,
    run_id: str,
    record_by_node: dict,
    art_store: ArtifactStore,
) -> str | None:
    """Get concatenated output artifact content for a node."""
    record = record_by_node.get(node_id)
    if record is None:
        return None
    parts: list[str] = []
    for art_id in record.output_artifact_refs:
        art = await art_store.get(art_id)
        if art is not None:
            # Shared renderer: a check must see the same text here as it would
            # as a per-node assertion.
            parts.append(checks.stringify(art.content))
    return "\n".join(parts) if parts else ""


async def _evaluate_one(
    idx: int,
    assert_def: EvalAssert,
    run_id: str,
    record_by_node: dict,
    terminal_nodes: list[str],
    art_store: ArtifactStore,
) -> AssertResult:
    t = assert_def.type

    # Resolve target nodes
    if assert_def.node is not None:
        target_nodes = [assert_def.node]
    else:
        target_nodes = terminal_nodes

    # Gather content from target nodes
    contents: list[str] = []
    for node_id in target_nodes:
        content = await _get_content_for_node(node_id, run_id, record_by_node, art_store)
        if content is None:
            if assert_def.node is not None:
                return AssertResult(
                    assert_index=idx,
                    type=t,
                    status="error",
                    reason=f"Node '{node_id}' not found in run '{run_id}'",
                )
        else:
            contents.append(content)

    combined = "\n".join(contents)

    try:
        if t == "contains":
            ok = checks.check_contains(combined, assert_def.value)  # type: ignore[arg-type]
            return AssertResult(
                assert_index=idx, type=t,
                status="passed" if ok else "failed",
                reason="" if ok else f"'{assert_def.value}' not found in output",
            )

        if t == "not_contains":
            ok = checks.check_not_contains(combined, assert_def.value)  # type: ignore[arg-type]
            return AssertResult(
                assert_index=idx, type=t,
                status="passed" if ok else "failed",
                reason=(
                    "" if ok
                    else f"'{assert_def.value}' found in output (should not be present)"
                ),
            )

        if t == "regex":
            ok = checks.check_regex(combined, assert_def.pattern)  # type: ignore[arg-type]
            return AssertResult(
                assert_index=idx, type=t,
                status="passed" if ok else "failed",
                reason="" if ok else f"Pattern '{assert_def.pattern}' not found in output",
            )

        if t == "json_path":
            return _eval_json_path(idx, assert_def, combined)

        if t == "llm_judge":
            return await _eval_llm_judge(idx, assert_def, combined)

    except Exception as exc:
        return AssertResult(assert_index=idx, type=t, status="error", reason=str(exc))

    return AssertResult(assert_index=idx, type=t, status="error", reason=f"Unknown type '{t}'")


def _eval_json_path(idx: int, assert_def: EvalAssert, content: str) -> AssertResult:
    from jsonpath_ng.ext import parse as jp_parse  # type: ignore[import-untyped]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return AssertResult(
            assert_index=idx, type="json_path", status="error",
            reason="Content is not valid JSON",
        )

    try:
        expr = jp_parse(assert_def.path)  # type: ignore[arg-type]
    except Exception as exc:
        return AssertResult(
            assert_index=idx, type="json_path", status="error",
            reason=f"Invalid JSONPath '{assert_def.path}': {exc}",
        )

    matches = expr.find(data)
    has_match = bool(matches)

    if assert_def.exists:
        ok = has_match
        reason = "" if ok else f"Path '{assert_def.path}' yielded no matches"
    else:
        ok = not has_match
        reason = "" if ok else f"Path '{assert_def.path}' matched (expected no match)"

    return AssertResult(
        assert_index=idx, type="json_path",
        status="passed" if ok else "failed",
        reason=reason,
    )


async def _call_llm_judge(content: str, prompt: str, model: str) -> dict[str, Any]:
    """Call litellm for an llm_judge assert. Returns {"pass": bool, "reason": str}."""
    import litellm  # type: ignore[import-untyped]

    system = (
        "You are an AI output evaluator. Respond ONLY with valid JSON: "
        '{"pass": true/false, "reason": "brief explanation"}. '
        "Do not include any other text."
    )
    user_msg = f"Output to evaluate:\n{content}\n\nEvaluation instruction:\n{prompt}"

    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = response.choices[0].message.content or ""
    return json.loads(raw)


async def _eval_llm_judge(idx: int, assert_def: EvalAssert, content: str) -> AssertResult:
    try:
        verdict = await _call_llm_judge(content, assert_def.prompt, assert_def.model)  # type: ignore[arg-type]
        passed = bool(verdict.get("pass"))
        reason = verdict.get("reason", "")
        return AssertResult(
            assert_index=idx, type="llm_judge",
            status="passed" if passed else "failed",
            reason=reason,
        )
    except Exception as exc:
        return AssertResult(
            assert_index=idx, type="llm_judge", status="error",
            reason=str(exc),
        )
