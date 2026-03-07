"""Workflow YAML/JSON loader — parses workflow files into WorkflowSpec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from binex.models.workflow import WorkflowSpec


def load_workflow(
    path: str | Path,
    *,
    user_vars: dict[str, str] | None = None,
) -> WorkflowSpec:
    """Load a workflow from a YAML or JSON file."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        fmt = "yaml"
    elif suffix == ".json":
        fmt = "json"
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")

    return load_workflow_from_string(
        path.read_text(), fmt=fmt, user_vars=user_vars,
    )


def load_workflow_from_string(
    content: str,
    *,
    fmt: str = "yaml",
    user_vars: dict[str, str] | None = None,
) -> WorkflowSpec:
    """Parse a workflow from a YAML or JSON string."""
    data = _parse_raw(content, fmt)
    try:
        spec = WorkflowSpec(**data)
    except ValidationError as exc:
        raise ValueError(f"Invalid workflow spec: {exc}") from exc
    return spec


def _parse_raw(content: str, fmt: str) -> dict[str, Any]:
    """Parse raw YAML or JSON string into a dict."""
    if fmt == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON: {exc}") from exc
    else:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Workflow spec must be a YAML/JSON mapping")
    return data
