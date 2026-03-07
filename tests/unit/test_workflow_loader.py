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
