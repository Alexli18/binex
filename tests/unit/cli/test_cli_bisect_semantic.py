"""`binex bisect --semantic`: opt-in, never silent about spending tokens."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore

COSMETIC = {
    "structure": {"changed": False, "confidence": "high", "reason": "same shape"},
    "facts": {"changed": False, "confidence": "high", "reason": "same claims"},
    "tone_format": {"changed": True, "confidence": "high", "reason": "reworded"},
}


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


async def _prose_runs():
    """One text node whose wording differs — 0.44 similarity, same meaning."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    texts = {
        "good": "The report is ready. Revenue grew 12% this quarter.",
        "bad": "The report is done. Revenue increased 12% over the quarter.",
    }
    for run_id, text in texts.items():
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=1, completed_nodes=1,
        ))
        await art_store.store(Artifact(
            id=f"art_{run_id}", run_id=run_id, type="result", content=text,
            lineage=Lineage(produced_by="draft"),
        ))
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}", run_id=run_id, task_id="draft",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            output_artifact_refs=[f"art_{run_id}"], latency_ms=10,
            trace_id=f"trace_{run_id}",
        ))
    return exec_store, art_store


def _invoke(runner: CliRunner, stores, *extra: str, judge=None, input_text=None):
    """Invoke `binex bisect` with a stubbed store and judge."""
    async def _fake_judge(a, b):
        return COSMETIC

    with (
        patch("binex.cli.bisect._get_stores", return_value=stores),
        patch(
            "binex.trace.semantic_judge.make_semantic_judge",
            return_value=judge or _fake_judge,
        ),
    ):
        return runner.invoke(
            cli, ["bisect", "good", "bad", "--no-rich", *extra], input=input_text,
        )


def test_semantic_flag_exists(runner: CliRunner):
    result = runner.invoke(cli, ["bisect", "runs", "--help"])
    assert result.exit_code == 0
    assert "--semantic" in result.output


def test_cost_is_shown_and_confirmed_before_any_call(runner: CliRunner):
    """Binex spending the user's tokens is never silent."""
    stores = asyncio.run(_prose_runs())

    result = _invoke(runner, stores, "--semantic", input_text="n\n")

    assert "judge call" in result.output.lower()
    assert "proceed" in result.output.lower()


def test_declining_the_prompt_runs_no_judge(runner: CliRunner):
    stores = asyncio.run(_prose_runs())
    calls = []

    async def _counting_judge(a, b):
        calls.append((a, b))
        return COSMETIC

    result = _invoke(
        runner, stores, "--semantic", judge=_counting_judge, input_text="n\n",
    )

    assert calls == []
    assert result.exit_code == 0


def test_yes_skips_the_prompt_and_judge_clears_the_node(runner: CliRunner):
    """0.44 similarity would be flagged; the judge says it is a reword."""
    stores = asyncio.run(_prose_runs())

    result = _invoke(runner, stores, "--semantic", "--yes")

    assert result.exit_code == 0
    assert "No differences" in result.output or "identical" in result.output


def test_without_the_flag_no_judge_and_node_is_flagged(runner: CliRunner):
    stores = asyncio.run(_prose_runs())
    calls = []

    async def _counting_judge(a, b):
        calls.append((a, b))
        return COSMETIC

    result = _invoke(runner, stores, judge=_counting_judge)

    assert calls == []
    assert "changed" in result.output


def test_verdict_line_states_why_the_judge_flagged_it(runner: CliRunner):
    """A ratio explains nothing; the judge's reason is the useful part."""
    stores = asyncio.run(_prose_runs())
    facts_changed = {
        "structure": {"changed": False, "confidence": "high", "reason": "same shape"},
        "facts": {"changed": True, "confidence": "high", "reason": "number changed"},
        "tone_format": {"changed": False, "confidence": "high", "reason": "same tone"},
    }

    async def _judge(a, b):
        return facts_changed

    result = _invoke(runner, stores, "--semantic", "--yes", judge=_judge)

    assert "draft" in result.output
    assert "facts" in result.output


def test_json_output_carries_the_verdict():
    import json

    stores = asyncio.run(_prose_runs())
    # Separate streams: the cost notice must not land in the JSON payload.
    runner = CliRunner(mix_stderr=False)

    result = _invoke(runner, stores, "--semantic", "--yes", "--json")

    assert "judge call" in result.stderr
    payload = json.loads(result.stdout)
    node = payload["node_map"][0]
    assert "semantic_verdict" in node
    assert "cosmetic" in node["semantic_verdict"]


def test_divergence_json_carries_the_reason():
    import json

    stores = asyncio.run(_prose_runs())
    facts_changed = {
        "structure": {"changed": False, "confidence": "high", "reason": "same shape"},
        "facts": {"changed": True, "confidence": "high", "reason": "number changed"},
        "tone_format": {"changed": False, "confidence": "high", "reason": "same tone"},
    }

    async def _judge(a, b):
        return facts_changed

    runner = CliRunner(mix_stderr=False)
    result = _invoke(runner, stores, "--semantic", "--yes", "--json", judge=_judge)

    payload = json.loads(result.stdout)
    assert payload["divergence"]["node_id"] == "draft"
    assert "facts" in payload["divergence"]["semantic_reason"]
