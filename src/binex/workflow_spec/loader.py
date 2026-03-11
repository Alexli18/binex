"""Workflow YAML/JSON loader — parses workflow files into WorkflowSpec."""

from __future__ import annotations

import json
import os
import re
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

    spec = load_workflow_from_string(
        path.read_text(), fmt=fmt, user_vars=user_vars,
        base_dir=path.parent,
    )
    spec.source_path = str(path)
    return spec


def load_workflow_from_string(
    content: str,
    *,
    fmt: str = "yaml",
    user_vars: dict[str, str] | None = None,
    base_dir: Path | None = None,
) -> WorkflowSpec:
    """Parse a workflow from a YAML or JSON string."""
    data = _parse_raw(content, fmt)
    _resolve_env_vars(data)
    if user_vars:
        _interpolate(data, user_vars)
    _resolve_file_prompts(data, base_dir=base_dir)
    try:
        spec = WorkflowSpec(**data)
    except ValidationError as exc:
        raise ValueError(f"Invalid workflow spec: {exc}") from exc
    return spec


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ${env.VAR} placeholders from environment variables."""
    if isinstance(obj, str):
        def _replace_env(match: re.Match) -> str:
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(
                    f"Environment variable '{var_name}' referenced in workflow "
                    f"via ${{env.{var_name}}} is not set"
                )
            return value
        return re.sub(r"\$\{env\.([^}]+)\}", _replace_env, obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = _resolve_env_vars(v)
        return obj
    if isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def _interpolate(obj: Any, user_vars: dict[str, str]) -> Any:
    """Recursively resolve ${user.key} placeholders in workflow data."""
    if isinstance(obj, str):
        for key, value in user_vars.items():
            obj = obj.replace(f"${{user.{key}}}", value)
        return obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = _interpolate(v, user_vars)
        return obj
    if isinstance(obj, list):
        return [_interpolate(item, user_vars) for item in obj]
    return obj


def _resolve_file_prompts(data: dict[str, Any], base_dir: Path | None = None) -> None:
    """Resolve file:// prefixed system_prompt values by reading file content."""
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        return

    for node_name, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue
        prompt = node_data.get("system_prompt")
        if not isinstance(prompt, str) or not prompt.startswith("file://"):
            continue

        file_path_str = prompt[len("file://"):]
        file_path = Path(file_path_str)

        if not file_path.is_absolute() and base_dir is not None:
            file_path = base_dir / file_path

        try:
            node_data["system_prompt"] = file_path.read_text()
        except FileNotFoundError:
            raise ValueError(
                f"Node '{node_name}': system_prompt file not found: {file_path}"
            )
        except OSError as exc:
            raise ValueError(
                f"Node '{node_name}': cannot read system_prompt file {file_path}: {exc}"
            ) from exc


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
