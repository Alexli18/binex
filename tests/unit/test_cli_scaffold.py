"""Tests for binex scaffold CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from binex.cli.scaffold import scaffold_group


class TestScaffoldAgent:
    def test_creates_all_expected_files(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "my-agent"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 0

        expected_files = [
            "__init__.py", "agent.py", "agent_card.json",
            "server.py", "requirements.txt",
        ]
        for fname in expected_files:
            assert (target / fname).exists(), f"{fname} was not created"

    def test_default_name_is_my_agent(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "my-agent"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 0

        card = json.loads((target / "agent_card.json").read_text())
        assert card["name"] == "my-agent"

        agent_py = (target / "agent.py").read_text()
        assert "my-agent" in agent_py or "my_agent" in agent_py

    def test_name_flag_changes_agent_name(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "cool-bot"
        result = runner.invoke(
            scaffold_group, ["agent", "--name", "cool-bot", "--dir", str(target)],
        )
        assert result.exit_code == 0

        card = json.loads((target / "agent_card.json").read_text())
        assert card["name"] == "cool-bot"

        agent_py = (target / "agent.py").read_text()
        assert "cool-bot" in agent_py or "cool_bot" in agent_py

        server_py = (target / "server.py").read_text()
        assert "cool-bot" in server_py or "cool_bot" in server_py

    def test_dir_flag_changes_target_directory(self, tmp_path: Path) -> None:
        runner = CliRunner()
        custom_dir = tmp_path / "custom" / "location"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(custom_dir)])
        assert result.exit_code == 0
        assert (custom_dir / "agent.py").exists()
        assert (custom_dir / "server.py").exists()

    def test_default_dir_uses_name(self, tmp_path: Path) -> None:
        """When --dir is not specified, the target directory is cwd/name."""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(scaffold_group, ["agent", "--name", "test-agent"])
            assert result.exit_code == 0
            assert (Path(td) / "test-agent" / "agent.py").exists()

    def test_fails_if_directory_already_has_files(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "existing"
        target.mkdir()
        (target / "something.txt").write_text("already here")

        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 1
        assert "already exists" in result.output.lower() or "not empty" in result.output.lower()

    def test_agent_card_is_valid_json(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "my-agent"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 0

        card = json.loads((target / "agent_card.json").read_text())
        assert "name" in card
        assert "description" in card
        assert "capabilities" in card

    def test_requirements_txt_has_dependencies(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "my-agent"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 0

        reqs = (target / "requirements.txt").read_text()
        assert "a2a-sdk" in reqs
        assert "fastapi" in reqs
        assert "uvicorn" in reqs

    def test_init_py_is_empty(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "my-agent"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 0
        assert (target / "__init__.py").read_text() == ""

    def test_success_message_printed(self, tmp_path: Path) -> None:
        runner = CliRunner()
        target = tmp_path / "my-agent"
        result = runner.invoke(scaffold_group, ["agent", "--dir", str(target)])
        assert result.exit_code == 0
        assert "scaffolded" in result.output.lower() or "created" in result.output.lower()
