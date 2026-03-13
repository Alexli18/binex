"""Tests for migration integration in workflow loader."""

import pytest

from binex.workflow_spec.loader import load_workflow_from_string
from binex.workflow_spec.migrations import UnsupportedVersionError


def test_loader_applies_migrations():
    """Loader should call migrate_workflow before Pydantic validation."""
    yaml_content = """
name: test
nodes:
  a:
    agent: "local://echo"
    outputs: [out]
"""
    spec = load_workflow_from_string(yaml_content)
    assert spec.version == 1


def test_loader_preserves_explicit_version():
    yaml_content = """
version: 1
name: test
nodes:
  a:
    agent: "local://echo"
    outputs: [out]
"""
    spec = load_workflow_from_string(yaml_content)
    assert spec.version == 1


def test_loader_rejects_future_version():
    yaml_content = """
version: 999
name: test
nodes:
  a:
    agent: "local://echo"
    outputs: [out]
"""
    with pytest.raises(ValueError, match="999"):
        load_workflow_from_string(yaml_content)
