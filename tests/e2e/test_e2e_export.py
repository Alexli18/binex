"""E2E tests for binex export command — real subprocess, real SQLite, real filesystem."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tests.e2e.conftest import extract_run_id, run_binex, write_workflow


SIMPLE_WORKFLOW = """\
name: export-test
nodes:
  greet:
    agent: "local://echo"
    inputs:
      message: "Hello from export test"
    outputs: [greeting]
"""


def _extract_run_id_from_output(output: str) -> str:
    """Extract run_id from binex output, handles both plain and Rich formats."""
    import re
    # Match "Run Id: run_xxxx" or "Run ID: run_xxxx" (Rich panel or plain text)
    m = re.search(r"Run\s+Id:\s+(run_\w+)", output, re.IGNORECASE)
    if m:
        return m.group(1)
    return extract_run_id(output)


@pytest.fixture
def run_with_data(binex_env, tmp_path):
    """Run a simple workflow and return (env, run_id, tmp_path)."""
    env, store_path, _ = binex_env
    wf_path = write_workflow(tmp_path, "export-test", SIMPLE_WORKFLOW)
    result = run_binex("run", str(wf_path), env=env, cwd=tmp_path)
    run_id = _extract_run_id_from_output(result.stdout + result.stderr)
    return env, run_id, tmp_path


class TestExportCsvE2E:
    def test_single_run_csv_export(self, run_with_data):
        """T050: single run CSV export."""
        env, run_id, tmp_path = run_with_data
        out_dir = tmp_path / "csv-export"

        result = run_binex(
            "export", run_id, "--output", str(out_dir), env=env, cwd=tmp_path,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert (out_dir / "runs.csv").exists()
        assert (out_dir / "records.csv").exists()
        assert (out_dir / "costs.csv").exists()

        # Verify CSV content
        with open(out_dir / "runs.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["run_id"] == run_id


class TestExportJsonE2E:
    def test_single_run_json_export(self, run_with_data):
        """T051: single run JSON export."""
        env, run_id, tmp_path = run_with_data
        out_dir = tmp_path / "json-export"

        result = run_binex(
            "export", run_id, "--format", "json",
            "--output", str(out_dir), env=env, cwd=tmp_path,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        export_file = out_dir / "export.json"
        assert export_file.exists()

        data = json.loads(export_file.read_text())
        assert "runs" in data
        assert "records" in data
        assert "costs" in data
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_id"] == run_id


class TestExportMultiRunE2E:
    def test_last_n_export(self, binex_env, tmp_path):
        """T052: --last N multi-run export."""
        env, store_path, _ = binex_env
        wf_path = write_workflow(tmp_path, "multi-test", SIMPLE_WORKFLOW)

        # Run workflow twice
        run_binex("run", str(wf_path), env=env, cwd=tmp_path)
        run_binex("run", str(wf_path), env=env, cwd=tmp_path)

        out_dir = tmp_path / "multi-export"
        result = run_binex(
            "export", "--last", "2", "--output", str(out_dir),
            env=env, cwd=tmp_path,
        )

        assert result.returncode == 0, f"stderr: {result.stderr}"
        with open(out_dir / "runs.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2


class TestExportErrorE2E:
    def test_nonexistent_run_error(self, binex_env, tmp_path):
        """T053: nonexistent run error."""
        env, _, _ = binex_env
        result = run_binex("export", "run_nonexistent", env=env, cwd=tmp_path)
        assert result.returncode != 0


class TestExportInHelp:
    def test_export_appears_in_help(self, binex_env):
        """T054: export appears in binex --help."""
        env, _, _ = binex_env
        result = run_binex("--help", env=env)
        assert result.returncode == 0
        assert "export" in result.stdout
