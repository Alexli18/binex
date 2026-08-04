"""Integration tests: full eval suite run with local:// agents (T018)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from binex.eval.loader import load_suite
from binex.eval.runner import run_suite
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def local_workflow(tmp_path: Path) -> Path:
    """A deterministic local:// workflow with a single node."""
    wf = tmp_path / "local-pipeline.yaml"
    wf.write_text(
        textwrap.dedent("""\
        name: local-pipeline
        nodes:
          worker:
            agent: local://echo
            system_prompt: "do work"
            inputs:
              data: "${user.input}"
            outputs: [result]
        """)
    )
    return wf


@pytest.fixture
def suite_file(tmp_path: Path, local_workflow: Path) -> Path:
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        textwrap.dedent(f"""\
        name: e2e-eval-suite
        workflow: {local_workflow}
        thresholds:
          min_similarity: 0.80
        cases:
          - id: case-alpha
            inputs:
              input: "hello world"
            asserts:
              - type: contains
                node: worker
                value: "no input"
          - id: case-beta
            inputs:
              input: "another test"
            asserts:
              - type: contains
                node: worker
                value: "msg"
        """)
    )
    return suite


@pytest.mark.asyncio
async def test_first_run_produces_no_baseline(suite_file: Path):
    """First run: no baselines → all verdicts are no_baseline (asserts pass)."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    suite = load_suite(suite_file)
    result = await run_suite(suite, exec_store=es, art_store=ats)

    assert result.total == 2
    assert result.no_baseline == 2
    assert result.failed == 0
    assert result.passed == 0
    # Each case has a run_id
    for case_result in result.cases:
        assert case_result.run_id is not None
        assert case_result.verdict == "no_baseline"


@pytest.mark.asyncio
async def test_bless_then_rerun_passes(suite_file: Path):
    """Bless baselines, then re-run: all cases should pass."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    suite = load_suite(suite_file)

    # First run
    first_result = await run_suite(suite, exec_store=es, art_store=ats)
    assert first_result.no_baseline == 2

    # Bless all cases
    for case_result in first_result.cases:
        await es.set_baseline(suite.name, case_result.case_id, case_result.run_id)

    # Second run
    second_result = await run_suite(suite, exec_store=es, art_store=ats)
    assert second_result.passed == 2
    assert second_result.failed == 0
    assert second_result.no_baseline == 0


@pytest.mark.asyncio
async def test_assert_failure_produces_fail_verdict(tmp_path: Path, local_workflow: Path):
    """A case with a failing assert should produce a fail verdict."""
    suite_file = tmp_path / "failing-suite.yaml"
    suite_file.write_text(
        textwrap.dedent(f"""\
        name: failing-suite
        workflow: {local_workflow}
        cases:
          - id: failing-case
            inputs:
              input: "hello world"
            asserts:
              - type: contains
                node: worker
                value: "XYZZY_NEVER_IN_OUTPUT_12345"
        """)
    )
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    suite = load_suite(suite_file)
    result = await run_suite(suite, exec_store=es, art_store=ats)

    assert result.cases[0].verdict == "fail"
    failed_asserts = [a for a in result.cases[0].assert_results if a.status == "failed"]
    assert len(failed_asserts) >= 1


@pytest.mark.asyncio
async def test_parallel_execution(suite_file: Path):
    """Parallel=2 should produce same results as sequential."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    suite = load_suite(suite_file)
    result = await run_suite(suite, parallel=2, exec_store=es, art_store=ats)
    assert result.total == 2


@pytest.mark.asyncio
async def test_eval_result_persisted(suite_file: Path):
    """EvalResult should be saved to the store after run_suite."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    suite = load_suite(suite_file)
    result = await run_suite(suite, exec_store=es, art_store=ats)

    # Should be persisted
    rows = await es.list_eval_results()
    assert len(rows) >= 1
    assert rows[0]["suite_name"] == "e2e-eval-suite"


@pytest.mark.asyncio
async def test_runs_tagged_with_eval_metadata(suite_file: Path):
    """Runs produced by eval should be tagged with eval_suite_id and eval_case_id."""
    es, ats = InMemoryExecutionStore(), InMemoryArtifactStore()
    suite = load_suite(suite_file)
    result = await run_suite(suite, exec_store=es, art_store=ats)

    for case_result in result.cases:
        run = await es.get_run(case_result.run_id)
        assert run is not None
        assert run.eval_suite_id == "e2e-eval-suite"
        assert run.eval_case_id == case_result.case_id
