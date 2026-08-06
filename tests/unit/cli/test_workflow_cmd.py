"""Tests for binex workflow CLI commands."""

from click.testing import CliRunner

from binex.cli.workflow_cmd import workflow_group


def test_workflow_version_shows_version(tmp_path):
    """binex workflow version <file> should display the workflow version."""
    wf = tmp_path / "test.yaml"
    wf.write_text(
        "version: 1\nname: test\nnodes:\n  a:\n"
        "    agent: local://echo\n    outputs: [out]\n"
    )

    runner = CliRunner()
    result = runner.invoke(workflow_group, ["version", str(wf)])
    assert result.exit_code == 0
    assert "Version: 1" in result.output
    assert "Workflow: test" in result.output


def test_workflow_version_default_when_missing(tmp_path):
    """When no version field, display default version 1."""
    wf = tmp_path / "test.yaml"
    wf.write_text(
        "name: test\nnodes:\n  a:\n"
        "    agent: local://echo\n    outputs: [out]\n"
    )

    runner = CliRunner()
    result = runner.invoke(workflow_group, ["version", str(wf)])
    assert result.exit_code == 0
    assert "1" in result.output
    assert "default" in result.output.lower()
