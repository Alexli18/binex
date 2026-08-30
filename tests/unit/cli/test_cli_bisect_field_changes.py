"""Field-level changes must reach the terminal, not just the similarity score.

The default (non-`--diff`) bisect view splits `content_diff` into good/bad
previews by reading unified-diff `-`/`+` prefixes. Field-change lines carry no
such prefixes, so without handling they render as nothing at all.
"""

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


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


async def _structured_runs():
    """Two runs whose node 'n' emitted a dict differing in one field."""
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    contents = {
        "good": {"decision": "approved", "reason": "all checks passed"},
        "bad": {"decision": "rejected", "reason": "all checks passed"},
    }
    for run_id, content in contents.items():
        await exec_store.create_run(RunSummary(
            run_id=run_id, workflow_name="wf", status="completed",
            total_nodes=1, completed_nodes=1,
        ))
        await art_store.store(Artifact(
            id=f"art_{run_id}", run_id=run_id, type="result", content=content,
            lineage=Lineage(produced_by="n"),
        ))
        await exec_store.record(ExecutionRecord(
            id=f"rec_{run_id}", run_id=run_id, task_id="n",
            agent_id="local://echo", status=TaskStatus.COMPLETED,
            output_artifact_refs=[f"art_{run_id}"], latency_ms=10,
            trace_id=f"trace_{run_id}",
        ))
    return exec_store, art_store


def _run_bisect(runner: CliRunner, stores, *extra: str):
    with patch("binex.cli.bisect._get_stores", return_value=stores):
        return runner.invoke(cli, ["bisect", "good", "bad", *extra])


def test_plain_output_names_the_changed_field(runner: CliRunner):
    stores = asyncio.run(_structured_runs())

    result = _run_bisect(runner, stores, "--no-rich")

    assert result.exit_code == 0
    assert "decision" in result.output
    assert "approved" in result.output
    assert "rejected" in result.output


def test_rich_output_names_the_changed_field(runner: CliRunner):
    stores = asyncio.run(_structured_runs())

    result = _run_bisect(runner, stores, "--rich")

    assert result.exit_code == 0
    assert "decision" in result.output


def test_diff_flag_shows_the_field_lines(runner: CliRunner):
    stores = asyncio.run(_structured_runs())

    result = _run_bisect(runner, stores, "--no-rich", "--diff")

    assert result.exit_code == 0
    assert "decision" in result.output
