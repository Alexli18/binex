"""Tests for CLI scheduler commands — list, add, remove."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from binex.cli.scheduler import scheduler_group


def _write_workflow(path: Path, name: str, schedule: str | None = None):
    data: dict = {"name": name, "nodes": {"a": {"agent": "local://echo", "outputs": ["r"]}}}
    if schedule is not None:
        data["schedule"] = schedule
    path.write_text(yaml.dump(data))


class TestSchedulerList:
    def test_list_empty_directory(self, tmp_path: Path):
        runner = CliRunner()
        result = runner.invoke(scheduler_group, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "No scheduled workflows" in result.output

    def test_list_finds_workflows(self, tmp_path: Path):
        _write_workflow(tmp_path / "report.yaml", "daily-report", "0 9 * * *")
        runner = CliRunner()
        result = runner.invoke(scheduler_group, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "daily-report" in result.output
        assert "0 9 * * *" in result.output

    def test_list_json_output(self, tmp_path: Path):
        _write_workflow(tmp_path / "report.yaml", "daily-report", "0 9 * * *")
        runner = CliRunner()
        result = runner.invoke(scheduler_group, ["list", str(tmp_path), "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "daily-report"
        assert data[0]["schedule"] == "0 9 * * *"
        assert "next_run" in data[0]

    def test_list_ignores_no_schedule(self, tmp_path: Path):
        _write_workflow(tmp_path / "plain.yaml", "plain-wf")
        runner = CliRunner()
        result = runner.invoke(scheduler_group, ["list", str(tmp_path)])
        assert result.exit_code == 0
        assert "No scheduled workflows" in result.output


class TestSchedulerAdd:
    def test_add_workflow(self, tmp_path: Path):
        wf = tmp_path / "report.yaml"
        _write_workflow(wf, "report", "*/5 * * * *")
        state_file = tmp_path / ".binex" / "scheduler.json"

        with patch("binex.cli.scheduler.DEFAULT_STATE_PATH", state_file):
            runner = CliRunner()
            result = runner.invoke(scheduler_group, ["add", str(wf)])
        assert result.exit_code == 0
        assert "Registered" in result.output

    def test_add_duplicate(self, tmp_path: Path):
        wf = tmp_path / "report.yaml"
        _write_workflow(wf, "report", "*/5 * * * *")
        state_file = tmp_path / ".binex" / "scheduler.json"

        with patch("binex.cli.scheduler.DEFAULT_STATE_PATH", state_file):
            runner = CliRunner()
            runner.invoke(scheduler_group, ["add", str(wf)])
            result = runner.invoke(scheduler_group, ["add", str(wf)])
        assert result.exit_code == 0
        assert "Already registered" in result.output


class TestSchedulerRemove:
    def test_remove_registered(self, tmp_path: Path):
        wf = tmp_path / "report.yaml"
        _write_workflow(wf, "report", "*/5 * * * *")
        state_file = tmp_path / ".binex" / "scheduler.json"

        with patch("binex.cli.scheduler.DEFAULT_STATE_PATH", state_file):
            runner = CliRunner()
            runner.invoke(scheduler_group, ["add", str(wf)])
            result = runner.invoke(scheduler_group, ["remove", str(wf)])
        assert result.exit_code == 0
        assert "Removed" in result.output

    def test_remove_not_registered(self, tmp_path: Path):
        state_file = tmp_path / ".binex" / "scheduler.json"
        with patch("binex.cli.scheduler.DEFAULT_STATE_PATH", state_file):
            runner = CliRunner()
            result = runner.invoke(scheduler_group, ["remove", "/nonexistent.yaml"])
        assert result.exit_code == 0
        assert "Not registered" in result.output
