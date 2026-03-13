"""Unit tests for binex export CLI command."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from binex.cli.main import cli
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_run(run_id: str = "run_abc") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        workflow_name="test-wf",
        workflow_path="test.yaml",
        status="completed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        total_nodes=2,
        completed_nodes=2,
        total_cost=0.05,
    )


def _make_record(run_id: str = "run_abc") -> ExecutionRecord:
    return ExecutionRecord(
        id="rec_1",
        run_id=run_id,
        task_id="node_a",
        agent_id="llm://gpt-4o",
        status="completed",
        latency_ms=1200,
        timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        trace_id="trace_1",
    )


def _make_cost(run_id: str = "run_abc") -> CostRecord:
    return CostRecord(
        id="cost_1",
        run_id=run_id,
        task_id="node_a",
        cost=0.05,
        source="llm_tokens",
        prompt_tokens=100,
        completion_tokens=50,
        model="gpt-4o",
        timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )


def _make_artifact(run_id: str = "run_abc") -> Artifact:
    return Artifact(
        id="art_1",
        run_id=run_id,
        type="text",
        content="Hello world",
        lineage=Lineage(produced_by="node_a"),
        created_at=datetime(2026, 1, 1, 0, 2, tzinfo=UTC),
    )


async def _populate_store(exec_store, art_store, run_id="run_abc"):
    """Populate stores with test data."""
    await exec_store.create_run(_make_run(run_id))
    await exec_store.record(_make_record(run_id))
    await exec_store.record_cost(_make_cost(run_id))
    art = _make_artifact(run_id)
    await art_store.store(art)


def _make_stores():
    return InMemoryExecutionStore(), InMemoryArtifactStore()


# ---- US1: Single run CSV export ----


class TestExportSingleRunCsv:
    def test_creates_output_dir_with_3_csv_files(self, tmp_path: Path):
        """T009: single run CSV export creates output dir with 3 CSV files."""
        exec_store, art_store = _make_stores()
        import asyncio
        asyncio.run(_populate_store(exec_store, art_store))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(cli, ["export", "run_abc", "--output", str(out_dir)])

        assert result.exit_code == 0, result.output
        assert (out_dir / "runs.csv").exists()
        assert (out_dir / "records.csv").exists()
        assert (out_dir / "costs.csv").exists()

        # Verify CSV content
        with open(out_dir / "runs.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["run_id"] == "run_abc"

    def test_nonexistent_run_returns_error(self):
        """T010: nonexistent run returns error exit code."""
        exec_store, art_store = _make_stores()

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            result = runner.invoke(cli, ["export", "run_nonexistent"])

        assert result.exit_code != 0

    def test_empty_costs_produce_csv_with_headers_only(self, tmp_path: Path):
        """T011: empty cost records produce CSV with headers only."""
        exec_store, art_store = _make_stores()
        import asyncio
        # Create run but no cost records
        asyncio.run(exec_store.create_run(_make_run()))
        asyncio.run(exec_store.record(_make_record()))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(cli, ["export", "run_abc", "--output", str(out_dir)])

        assert result.exit_code == 0
        with open(out_dir / "costs.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0
        # Headers should still exist
        with open(out_dir / "costs.csv") as f:
            header = f.readline().strip()
        assert "cost" in header


# ---- US2: JSON export ----


class TestExportJsonFormat:
    def test_json_export_creates_export_json(self, tmp_path: Path):
        """T017: JSON export creates export.json with correct structure."""
        exec_store, art_store = _make_stores()
        import asyncio
        asyncio.run(_populate_store(exec_store, art_store))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(
                cli, ["export", "run_abc", "--format", "json", "--output", str(out_dir)],
            )

        assert result.exit_code == 0, result.output
        export_file = out_dir / "export.json"
        assert export_file.exists()
        data = json.loads(export_file.read_text())
        assert "runs" in data
        assert "records" in data
        assert "costs" in data
        assert len(data["runs"]) == 1


# ---- US3: Multi-run export ----


class TestExportMultiRun:
    def test_last_n_exports_multiple_runs(self, tmp_path: Path):
        """T021: --last N exports multiple runs to CSV."""
        exec_store, art_store = _make_stores()
        import asyncio
        asyncio.run(_populate_store(exec_store, art_store, "run_1"))
        asyncio.run(_populate_store(exec_store, art_store, "run_2"))
        asyncio.run(_populate_store(exec_store, art_store, "run_3"))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(cli, ["export", "--last", "2", "--output", str(out_dir)])

        assert result.exit_code == 0, result.output
        with open(out_dir / "runs.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2

    def test_last_n_greater_than_total_exports_all(self, tmp_path: Path):
        """T022: --last N with N > total runs exports all without error."""
        exec_store, art_store = _make_stores()
        import asyncio
        asyncio.run(_populate_store(exec_store, art_store, "run_1"))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(cli, ["export", "--last", "100", "--output", str(out_dir)])

        assert result.exit_code == 0
        with open(out_dir / "runs.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1


# ---- US4: Export with artifacts ----


class TestExportWithArtifacts:
    def test_include_artifacts_adds_artifacts_json_to_csv(self, tmp_path: Path):
        """T026: --include-artifacts adds artifacts.json to CSV export."""
        exec_store, art_store = _make_stores()
        import asyncio
        asyncio.run(_populate_store(exec_store, art_store))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(
                cli, ["export", "run_abc", "--include-artifacts", "--output", str(out_dir)],
            )

        assert result.exit_code == 0, result.output
        assert (out_dir / "artifacts.json").exists()
        data = json.loads((out_dir / "artifacts.json").read_text())
        assert len(data) == 1
        assert data[0]["content"] == "Hello world"

    def test_include_artifacts_with_json_format(self, tmp_path: Path):
        """T027: --include-artifacts with --format json includes artifacts in export.json."""
        exec_store, art_store = _make_stores()
        import asyncio
        asyncio.run(_populate_store(exec_store, art_store))

        with patch("binex.cli.export_cmd._get_stores", return_value=(exec_store, art_store)):
            runner = CliRunner()
            out_dir = tmp_path / "out"
            result = runner.invoke(
                cli,
                ["export", "run_abc", "--format", "json",
                 "--include-artifacts", "--output", str(out_dir)],
            )

        assert result.exit_code == 0, result.output
        data = json.loads((out_dir / "export.json").read_text())
        assert "artifacts" in data
        assert len(data["artifacts"]) == 1
