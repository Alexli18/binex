"""Tests for binex validate CLI command."""

from __future__ import annotations

import json
import textwrap

from click.testing import CliRunner

from binex.cli.validate import validate_cmd


def _valid_workflow_yaml() -> str:
    return textwrap.dedent("""\
        name: test-workflow
        nodes:
          fetch:
            agent: local://fetch
            outputs: [data]
          analyse:
            agent: local://analyse
            depends_on: [fetch]
            outputs: [report]
    """)


def _cycle_workflow_yaml() -> str:
    return textwrap.dedent("""\
        name: cycle-workflow
        nodes:
          a:
            agent: local://a
            depends_on: [b]
            outputs: [x]
          b:
            agent: local://b
            depends_on: [a]
            outputs: [y]
    """)


def _missing_ref_workflow_yaml() -> str:
    return textwrap.dedent("""\
        name: bad-ref
        nodes:
          a:
            agent: local://a
            depends_on: [nonexistent]
            outputs: [x]
    """)


class TestValidateValidWorkflow:
    def test_success_output(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_valid_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "Valid" in result.output
        assert "2" in result.output  # 2 nodes
        assert "fetch" in result.output or "analyse" in result.output

    def test_success_shows_edge_count(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_valid_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 0
        # analyse depends on fetch => 1 edge
        assert "1" in result.output

    def test_success_shows_agents(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_valid_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 0
        assert "local://fetch" in result.output
        assert "local://analyse" in result.output


class TestValidateInvalidWorkflow:
    def test_cycle_error(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_cycle_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 2
        assert "cycle" in result.output.lower()

    def test_missing_ref_error(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_missing_ref_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 2
        assert "nonexistent" in result.output


class TestValidateYamlParseError:
    def test_bad_yaml(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text("name: [\ninvalid yaml {{{\n")

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 2
        assert "error" in result.output.lower()

    def test_not_a_mapping(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text("- just\n- a\n- list\n")

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf)])

        assert result.exit_code == 2


class TestValidateJsonOutput:
    def test_valid_json_output(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_valid_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf), "--json"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["valid"] is True
        assert parsed["node_count"] == 2
        assert parsed["edge_count"] == 1
        assert set(parsed["agents"]) == {"local://fetch", "local://analyse"}

    def test_invalid_json_output(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text(_cycle_workflow_yaml())

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf), "--json"])

        assert result.exit_code == 2
        parsed = json.loads(result.output)
        assert parsed["valid"] is False
        assert len(parsed["errors"]) > 0

    def test_parse_error_json_output(self, tmp_path) -> None:
        wf = tmp_path / "wf.yaml"
        wf.write_text("name: [\ninvalid yaml {{{\n")

        runner = CliRunner()
        result = runner.invoke(validate_cmd, [str(wf), "--json"])

        assert result.exit_code == 2
        parsed = json.loads(result.output)
        assert parsed["valid"] is False
        assert len(parsed["errors"]) > 0
