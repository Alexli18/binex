"""Tests for CLI trace and artifacts commands (T037, T038)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

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


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 3, 7, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_stores(base_time: datetime):
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()

    import asyncio

    async def _populate():
        await exec_store.create_run(RunSummary(
            run_id="run_001",
            workflow_name="test-pipeline",
            status="completed",
            started_at=base_time,
            completed_at=base_time + timedelta(seconds=5),
            total_nodes=2,
            completed_nodes=2,
        ))
        await exec_store.record(ExecutionRecord(
            id="rec_1",
            run_id="run_001",
            task_id="planner",
            agent_id="local://planner",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=[],
            output_artifact_refs=["art_plan"],
            latency_ms=1200,
            timestamp=base_time,
            trace_id="trace_001",
        ))
        await exec_store.record(ExecutionRecord(
            id="rec_2",
            run_id="run_001",
            task_id="researcher",
            agent_id="local://researcher",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=["art_plan"],
            output_artifact_refs=["art_research"],
            latency_ms=2500,
            timestamp=base_time + timedelta(seconds=1),
            trace_id="trace_001",
        ))

        await art_store.store(Artifact(
            id="art_plan",
            run_id="run_001",
            type="execution_plan",
            content={"steps": ["search"]},
            lineage=Lineage(produced_by="planner", derived_from=[]),
        ))
        await art_store.store(Artifact(
            id="art_research",
            run_id="run_001",
            type="search_results",
            content={"results": ["paper1"]},
            lineage=Lineage(produced_by="researcher", derived_from=["art_plan"]),
        ))

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_populate())
    return exec_store, art_store


# --- T037: binex trace ---

class TestTraceCommand:
    def test_trace_shows_timeline(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.trace._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["trace", "run_001"])
        assert result.exit_code == 0
        assert "planner" in result.output
        assert "researcher" in result.output

    def test_trace_json_output(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.trace._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["trace", "run_001", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_trace_node_shows_single_step(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.trace._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["trace", "node", "run_001", "planner"])
        assert result.exit_code == 0
        assert "planner" in result.output
        assert "1200" in result.output

    def test_trace_node_not_found(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.trace._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["trace", "node", "run_001", "nonexistent"])
        assert result.exit_code != 0

    def test_trace_graph_shows_dag(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.trace._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["trace", "graph", "run_001"])
        assert result.exit_code == 0
        assert "planner" in result.output
        assert "researcher" in result.output

    def test_trace_graph_json_output(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.trace._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["trace", "graph", "run_001", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 2


# --- T038: binex artifacts ---

class TestArtifactsCommand:
    def test_artifacts_list(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "list", "run_001"])
        assert result.exit_code == 0
        assert "art_plan" in result.output
        assert "art_research" in result.output

    def test_artifacts_list_json(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "list", "run_001", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_artifacts_show(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "show", "art_plan"])
        assert result.exit_code == 0
        assert "execution_plan" in result.output
        assert "search" in result.output

    def test_artifacts_show_not_found(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "show", "nonexistent"])
        assert result.exit_code != 0

    def test_artifacts_lineage(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "lineage", "art_research"])
        assert result.exit_code == 0
        assert "art_research" in result.output
        assert "art_plan" in result.output

    def test_artifacts_lineage_json(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "lineage", "art_research", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert data["artifact_id"] == "art_research"

    def test_artifacts_lineage_not_found(self, runner: CliRunner, mock_stores) -> None:
        exec_store, art_store = mock_stores
        with patch("binex.cli.artifacts._get_stores", return_value=(exec_store, art_store)):
            result = runner.invoke(cli, ["artifacts", "lineage", "nonexistent"])
        assert result.exit_code != 0
