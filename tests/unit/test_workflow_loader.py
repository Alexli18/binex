"""Tests for workflow YAML/JSON loader."""

from __future__ import annotations

import json
import os
import tempfile

import pytest
import yaml

from binex.workflow_spec.loader import load_workflow, load_workflow_from_string


def test_load_from_yaml_string(sample_workflow_dict: dict) -> None:
    yaml_str = yaml.dump(sample_workflow_dict)
    spec = load_workflow_from_string(yaml_str, fmt="yaml")
    assert spec.name == "test-workflow"
    assert len(spec.nodes) == 2
    assert "producer" in spec.nodes
    assert "consumer" in spec.nodes


def test_load_from_json_string(sample_workflow_dict: dict) -> None:
    json_str = json.dumps(sample_workflow_dict)
    spec = load_workflow_from_string(json_str, fmt="json")
    assert spec.name == "test-workflow"
    assert len(spec.nodes) == 2


def test_load_from_yaml_file(sample_workflow_dict: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_workflow_dict, f)
        path = f.name
    try:
        spec = load_workflow(path)
        assert spec.name == "test-workflow"
        assert len(spec.nodes) == 2
    finally:
        os.unlink(path)


def test_load_from_json_file(sample_workflow_dict: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_workflow_dict, f)
        path = f.name
    try:
        spec = load_workflow(path)
        assert spec.name == "test-workflow"
    finally:
        os.unlink(path)


def test_load_research_pipeline(sample_research_workflow_dict: dict) -> None:
    yaml_str = yaml.dump(sample_research_workflow_dict)
    spec = load_workflow_from_string(yaml_str, fmt="yaml")
    assert spec.name == "research-pipeline"
    assert len(spec.nodes) == 5
    assert spec.nodes["validator"].retry_policy is not None
    assert spec.nodes["validator"].retry_policy.max_retries == 2


def test_node_ids_populated(sample_workflow_dict: dict) -> None:
    yaml_str = yaml.dump(sample_workflow_dict)
    spec = load_workflow_from_string(yaml_str, fmt="yaml")
    assert spec.nodes["producer"].id == "producer"
    assert spec.nodes["consumer"].id == "consumer"


def test_load_invalid_yaml() -> None:
    with pytest.raises(ValueError, match="parse|Invalid"):
        load_workflow_from_string("{invalid yaml: [}", fmt="yaml")


def test_load_missing_required_fields() -> None:
    with pytest.raises(Exception):
        load_workflow_from_string('{"nodes": {}}', fmt="json")


def test_load_unsupported_extension() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("hello")
        path = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported"):
            load_workflow(path)
    finally:
        os.unlink(path)


def test_load_with_user_vars(sample_workflow_dict: dict) -> None:
    yaml_str = yaml.dump(sample_workflow_dict)
    spec = load_workflow_from_string(yaml_str, fmt="yaml", user_vars={"input": "hello"})
    assert spec.name == "test-workflow"


def test_env_var_resolution(sample_workflow_dict: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-secret-123")
    sample_workflow_dict["nodes"]["producer"]["config"] = {"api_key": "${env.TEST_API_KEY}"}
    yaml_str = yaml.dump(sample_workflow_dict)
    spec = load_workflow_from_string(yaml_str, fmt="yaml")
    assert spec.nodes["producer"].config["api_key"] == "sk-secret-123"


def test_env_var_missing_raises(sample_workflow_dict: dict) -> None:
    sample_workflow_dict["nodes"]["producer"]["config"] = {"api_key": "${env.NONEXISTENT_VAR_XYZ}"}
    yaml_str = yaml.dump(sample_workflow_dict)
    with pytest.raises(ValueError, match="NONEXISTENT_VAR_XYZ.*is not set"):
        load_workflow_from_string(yaml_str, fmt="yaml")


def test_env_var_mixed_with_user_vars(
    sample_workflow_dict: dict, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MY_KEY", "secret")
    sample_workflow_dict["nodes"]["producer"]["config"] = {"api_key": "${env.MY_KEY}"}
    sample_workflow_dict["nodes"]["producer"]["inputs"] = {"topic": "${user.topic}"}
    yaml_str = yaml.dump(sample_workflow_dict)
    spec = load_workflow_from_string(yaml_str, fmt="yaml", user_vars={"topic": "AI"})
    assert spec.nodes["producer"].config["api_key"] == "secret"
    assert spec.nodes["producer"].inputs["topic"] == "AI"


class TestResolveFilePrompts:
    """Tests for file:// system_prompt resolution."""

    def test_resolve_file_prompt_relative(self, tmp_path):
        """Relative file:// path resolves relative to base_dir."""
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "agent.md").write_text("You are a helpful agent.")

        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": "file://prompts/agent.md",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts
        _resolve_file_prompts(data, base_dir=tmp_path)
        assert data["nodes"]["a"]["system_prompt"] == "You are a helpful agent."

    def test_resolve_file_prompt_absolute(self, tmp_path):
        """Absolute file:// path is used as-is."""
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Absolute prompt content.")

        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": f"file://{prompt_file}",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts
        _resolve_file_prompts(data, base_dir=tmp_path)
        assert data["nodes"]["a"]["system_prompt"] == "Absolute prompt content."

    def test_resolve_file_prompt_not_found(self, tmp_path):
        """Missing file raises ValueError with node name and path."""
        data = {
            "name": "test",
            "nodes": {
                "researcher": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": "file://missing.md",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts
        with pytest.raises(ValueError, match="researcher"):
            _resolve_file_prompts(data, base_dir=tmp_path)

    def test_plain_system_prompt_unchanged(self, tmp_path):
        """Plain string system_prompt is not affected."""
        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "system_prompt": "Just a regular prompt",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts
        _resolve_file_prompts(data, base_dir=tmp_path)
        assert data["nodes"]["a"]["system_prompt"] == "Just a regular prompt"

    def test_no_system_prompt_unchanged(self, tmp_path):
        """Node without system_prompt is not affected."""
        data = {
            "name": "test",
            "nodes": {
                "a": {
                    "agent": "llm://openai/gpt-4",
                    "outputs": ["out"],
                }
            },
        }

        from binex.workflow_spec.loader import _resolve_file_prompts
        _resolve_file_prompts(data, base_dir=tmp_path)
        assert "system_prompt" not in data["nodes"]["a"]


class TestLoadWorkflowFilePrompt:
    """Integration: load_workflow resolves file:// system_prompt."""

    def test_load_workflow_resolves_file_prompt(self, tmp_path):
        """Full load_workflow pipeline resolves file:// prompts."""
        prompt_dir = tmp_path / "prompts"
        prompt_dir.mkdir()
        (prompt_dir / "researcher.md").write_text("You are a researcher.")

        workflow_yaml = tmp_path / "workflow.yaml"
        workflow_yaml.write_text(
            'name: test-workflow\nnodes:\n  researcher:\n    agent: llm://openai/gpt-4\n    system_prompt: "file://prompts/researcher.md"\n    outputs: [result]\n'
        )

        from binex.workflow_spec.loader import load_workflow

        spec = load_workflow(workflow_yaml)
        assert spec.nodes["researcher"].system_prompt == "You are a researcher."
