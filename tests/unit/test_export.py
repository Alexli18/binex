"""Unit tests for export serializers (CSV/JSON writers)."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord
from binex.models.execution import ExecutionRecord, RunSummary


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


# ---- CSV writer tests ----


class TestWriteRunsCsv:
    def test_writes_csv_with_headers_and_data(self, tmp_path: Path):
        from binex.export import write_runs_csv

        path = tmp_path / "runs.csv"
        write_runs_csv([_make_run()], path)

        assert path.exists()
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["run_id"] == "run_abc"
        assert rows[0]["workflow_name"] == "test-wf"
        assert rows[0]["status"] == "completed"

    def test_empty_list_writes_headers_only(self, tmp_path: Path):
        from binex.export import write_runs_csv

        path = tmp_path / "runs.csv"
        write_runs_csv([], path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0
        # Headers should still exist
        with open(path) as f:
            header = f.readline().strip()
        assert "run_id" in header

    def test_multiple_runs(self, tmp_path: Path):
        from binex.export import write_runs_csv

        path = tmp_path / "runs.csv"
        runs = [_make_run("run_1"), _make_run("run_2")]
        write_runs_csv(runs, path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2


class TestWriteRecordsCsv:
    def test_writes_records_csv(self, tmp_path: Path):
        from binex.export import write_records_csv

        path = tmp_path / "records.csv"
        write_records_csv([_make_record()], path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["task_id"] == "node_a"
        assert rows[0]["agent_id"] == "llm://gpt-4o"

    def test_empty_records(self, tmp_path: Path):
        from binex.export import write_records_csv

        path = tmp_path / "records.csv"
        write_records_csv([], path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0


class TestWriteCostsCsv:
    def test_writes_costs_csv(self, tmp_path: Path):
        from binex.export import write_costs_csv

        path = tmp_path / "costs.csv"
        write_costs_csv([_make_cost()], path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["task_id"] == "node_a"
        assert float(rows[0]["cost"]) == 0.05

    def test_empty_costs(self, tmp_path: Path):
        from binex.export import write_costs_csv

        path = tmp_path / "costs.csv"
        write_costs_csv([], path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0


# ---- JSON writer tests ----


class TestWriteJson:
    def test_writes_json_with_all_sections(self, tmp_path: Path):
        from binex.export import write_json

        path = tmp_path / "export.json"
        write_json(
            runs=[_make_run()],
            records=[_make_record()],
            costs=[_make_cost()],
            path=path,
        )

        data = json.loads(path.read_text())
        assert "runs" in data
        assert "records" in data
        assert "costs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_id"] == "run_abc"

    def test_json_with_artifacts(self, tmp_path: Path):
        from binex.export import write_json

        path = tmp_path / "export.json"
        write_json(
            runs=[_make_run()],
            records=[_make_record()],
            costs=[_make_cost()],
            path=path,
            artifacts=[_make_artifact()],
        )

        data = json.loads(path.read_text())
        assert "artifacts" in data
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["content"] == "Hello world"

    def test_json_without_artifacts(self, tmp_path: Path):
        from binex.export import write_json

        path = tmp_path / "export.json"
        write_json(
            runs=[_make_run()],
            records=[],
            costs=[],
            path=path,
        )

        data = json.loads(path.read_text())
        assert "artifacts" not in data

    def test_empty_data(self, tmp_path: Path):
        from binex.export import write_json

        path = tmp_path / "export.json"
        write_json(runs=[], records=[], costs=[], path=path)

        data = json.loads(path.read_text())
        assert data["runs"] == []
        assert data["records"] == []
        assert data["costs"] == []
