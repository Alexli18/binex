"""Tests for src/binex/eval/asserts.py (T010, T017)."""

from __future__ import annotations

import json

import pytest

from binex.eval.asserts import evaluate_asserts
from binex.eval.models import EvalAssert, EvalCase
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_run(run_id: str = "run_test", *, node_ids: list[str] | None = None) -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test",
        status="completed",
        total_nodes=len(node_ids or []),
    )


def make_record(run_id: str, node_id: str, output_refs: list[str]) -> ExecutionRecord:
    return ExecutionRecord(
        id=f"rec_{node_id}",
        run_id=run_id,
        task_id=node_id,
        agent_id="local://echo",
        status=TaskStatus.COMPLETED,
        output_artifact_refs=output_refs,
        latency_ms=10,
        trace_id="trace_test",
    )


def make_artifact(
    art_id: str, run_id: str, produced_by: str, content: str, art_type: str = "output"
) -> Artifact:
    return Artifact(
        id=art_id,
        run_id=run_id,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=produced_by),
    )


async def _setup_run(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    run_id: str = "run_test",
    node_id: str = "worker",
    content: str = "hello world",
) -> None:
    art_id = f"art_{node_id}"
    run = make_run(run_id, node_ids=[node_id])
    await exec_store.create_run(run)
    await exec_store.record(make_record(run_id, node_id, [art_id]))
    await art_store.store(make_artifact(art_id, run_id, node_id, content))


# ---------------------------------------------------------------------------
# contains
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_contains_pass():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="hello world")
    case = EvalCase(id="c", asserts=[EvalAssert(type="contains", value="hello", node="worker")])
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert len(results) == 1
    assert results[0].status == "passed"


@pytest.mark.asyncio
async def test_contains_fail():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="hello world")
    case = EvalCase(id="c", asserts=[EvalAssert(type="contains", value="missing", node="worker")])
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "failed"


# ---------------------------------------------------------------------------
# not_contains
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_not_contains_pass():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="hello world")
    case = EvalCase(
        id="c", asserts=[EvalAssert(type="not_contains", value="error", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "passed"


@pytest.mark.asyncio
async def test_not_contains_fail():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="fatal error occurred")
    case = EvalCase(
        id="c", asserts=[EvalAssert(type="not_contains", value="error", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "failed"


# ---------------------------------------------------------------------------
# regex
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regex_pass():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="result: 2024")
    case = EvalCase(id="c", asserts=[EvalAssert(type="regex", pattern=r"\d{4}", node="worker")])
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "passed"


@pytest.mark.asyncio
async def test_regex_fail():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="no digits here")
    case = EvalCase(id="c", asserts=[EvalAssert(type="regex", pattern=r"\d{4}", node="worker")])
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "failed"


# ---------------------------------------------------------------------------
# json_path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_json_path_exists_pass():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content=json.dumps({"questions": ["q1", "q2"]}))
    case = EvalCase(
        id="c", asserts=[EvalAssert(type="json_path", path="$.questions", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "passed"


@pytest.mark.asyncio
async def test_json_path_exists_fail():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content=json.dumps({"other": "value"}))
    case = EvalCase(
        id="c", asserts=[EvalAssert(type="json_path", path="$.questions", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "failed"


@pytest.mark.asyncio
async def test_json_path_not_exists_pass():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content=json.dumps({"other": "x"}))
    case = EvalCase(
        id="c",
        asserts=[EvalAssert(type="json_path", path="$.questions", exists=False, node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "passed"


# ---------------------------------------------------------------------------
# default node (terminal node)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_default_node_uses_terminal():
    """When node is None, assert should target the terminal node(s)."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    run_id = "run_t"
    art_id = "art_terminal"
    run = make_run(run_id, node_ids=["step1", "terminal"])
    await es.create_run(run)
    # step1 produces art_step1, terminal derives from it
    await es.record(make_record(run_id, "step1", ["art_step1"]))
    await es.record(make_record(run_id, "terminal", [art_id]))
    await art_store_store(ats, "art_step1", run_id, "step1", "intermediate")
    await art_store_store(ats, art_id, run_id, "terminal", "final output hello")
    # Assert without node= should check "terminal" node's artifact
    case = EvalCase(id="c", asserts=[EvalAssert(type="contains", value="hello")])
    results = await evaluate_asserts(case, run_id, es, ats)
    assert results[0].status == "passed"


async def art_store_store(ats, art_id, run_id, produced_by, content):
    await ats.store(make_artifact(art_id, run_id, produced_by, content))


# ---------------------------------------------------------------------------
# node not found → error status (not failed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_node_not_found_is_error():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, node_id="worker", content="hi")
    case = EvalCase(
        id="c", asserts=[EvalAssert(type="contains", value="hi", node="nonexistent_node")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "error"
    assert "nonexistent_node" in results[0].reason


# ---------------------------------------------------------------------------
# multiple asserts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_asserts_all_evaluated():
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="hello world 2024")
    case = EvalCase(
        id="c",
        asserts=[
            EvalAssert(type="contains", value="hello", node="worker"),
            EvalAssert(type="regex", pattern=r"\d{4}", node="worker"),
            EvalAssert(type="contains", value="missing", node="worker"),
        ],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert len(results) == 3
    assert results[0].status == "passed"
    assert results[1].status == "passed"
    assert results[2].status == "failed"
    # assert_index is set correctly
    assert results[0].assert_index == 0
    assert results[2].assert_index == 2


# ---------------------------------------------------------------------------
# llm_judge — transport/parse failure → error (not failed)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_llm_judge_error_on_bad_response(monkeypatch):
    """When litellm call fails or returns unparseable response, status=error."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="some output")

    async def _bad_completion(*args, **kwargs):
        raise RuntimeError("LLM unreachable")

    import binex.eval.asserts as asserts_mod
    monkeypatch.setattr(asserts_mod, "_call_llm_judge", _bad_completion)

    case = EvalCase(
        id="c",
        asserts=[EvalAssert(type="llm_judge", prompt="Is it good?", model="x/y", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "error"
    assert "LLM unreachable" in results[0].reason


@pytest.mark.asyncio
async def test_llm_judge_pass(monkeypatch):
    """When judge returns {pass: true}, status=passed."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="some output")

    async def _good_completion(content: str, prompt: str, model: str) -> dict:
        return {"pass": True, "reason": "looks good"}

    import binex.eval.asserts as asserts_mod
    monkeypatch.setattr(asserts_mod, "_call_llm_judge", _good_completion)

    case = EvalCase(
        id="c",
        asserts=[EvalAssert(type="llm_judge", prompt="Is it good?", model="x/y", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "passed"


@pytest.mark.asyncio
async def test_llm_judge_fail(monkeypatch):
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    await _setup_run(es, ats, content="bad output")

    async def _fail_completion(content: str, prompt: str, model: str) -> dict:
        return {"pass": False, "reason": "does not cite sources"}

    import binex.eval.asserts as asserts_mod
    monkeypatch.setattr(asserts_mod, "_call_llm_judge", _fail_completion)

    case = EvalCase(
        id="c",
        asserts=[EvalAssert(type="llm_judge", prompt="Cite sources?", model="x/y", node="worker")],
    )
    results = await evaluate_asserts(case, "run_test", es, ats)
    assert results[0].status == "failed"
    assert "does not cite sources" in results[0].reason
