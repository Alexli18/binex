"""Tests for `binex explore` interactive browser."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import RunSummary
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_stores(runs=None, artifacts=None):
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    async def setup():
        for r in (runs or []):
            await exec_store.create_run(r)
        for a in (artifacts or []):
            await art_store.store(a)

    import asyncio
    asyncio.run(setup())
    return exec_store, art_store


def _run(run_id="run_abc123", name="test-workflow", status="completed"):
    return RunSummary(
        run_id=run_id,
        workflow_name=name,
        status=status,
        started_at=datetime.now(UTC),
        total_nodes=2,
        completed_nodes=2,
    )


def _artifact(art_id="art_1", run_id="run_abc123", node="producer", atype="text", content="hello"):
    return Artifact(
        id=art_id,
        run_id=run_id,
        type=atype,
        content=content,
        status="complete",
        lineage=Lineage(produced_by=node),
    )


PATCH_TARGET = "binex.cli.explore._get_stores"


class TestExploreNoRuns:
    def test_no_runs_shows_help(self):
        stores = _make_stores()
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "No runs found" in result.output


class TestExploreRunSelection:
    def test_lists_runs_and_quit(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "test-workflow" in result.output
        assert "run_abc123" in result.output

    def test_select_run_then_quit(self):
        stores = _make_stores(
            runs=[_run()],
            artifacts=[_artifact()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="1\nq\n")
        assert "producer" in result.output

    def test_invalid_choice_reprompts(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="99\nq\n")
        assert "Invalid choice" in result.output


class TestExploreDirectRunId:
    def test_jump_to_artifacts(self):
        stores = _make_stores(
            runs=[_run()],
            artifacts=[_artifact()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "producer" in result.output

    def test_no_artifacts_for_run(self):
        stores = _make_stores(runs=[_run()])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"])
        assert "No artifacts found" in result.output


class TestExploreArtifactDetail:
    def test_show_artifact_content(self):
        stores = _make_stores(
            runs=[_run()],
            artifacts=[_artifact(content="Hello World!")],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="1\nb\nq\n")
        assert "Hello World!" in result.output

    def test_lineage_action(self):
        stores = _make_stores(
            runs=[_run()],
            artifacts=[_artifact()],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="1\nl\nb\nq\n")
        assert result.exit_code == 0


class TestExploreMultipleRuns:
    def test_multiple_runs_sorted(self):
        r1 = _run("run_old", "old-wf")
        r2 = _run("run_new", "new-wf")
        stores = _make_stores(runs=[r1, r2])
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore"], input="q\n")
        assert "old-wf" in result.output
        assert "new-wf" in result.output


class TestExploreMultipleArtifacts:
    def test_two_artifacts_listed(self):
        stores = _make_stores(
            runs=[_run()],
            artifacts=[
                _artifact("art_1", node="producer", content="first"),
                _artifact("art_2", node="consumer", content="second"),
            ],
        )
        runner = CliRunner()
        with patch(PATCH_TARGET, return_value=stores):
            result = runner.invoke(cli, ["explore", "run_abc123"], input="q\n")
        assert "producer" in result.output
        assert "consumer" in result.output
