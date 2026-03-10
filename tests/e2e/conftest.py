"""Shared fixtures for real E2E tests — no mocks, real SQLite + filesystem."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def binex_env(tmp_path):
    """Isolated binex environment with real SQLite + filesystem stores.

    Sets BINEX_STORE_PATH to a temp directory so each test gets fresh storage.
    Returns (env_dict, store_path, tmp_path).
    """
    store_path = tmp_path / ".binex"
    store_path.mkdir()

    env = os.environ.copy()
    env["BINEX_STORE_PATH"] = str(store_path)

    return env, store_path, tmp_path


def run_binex(*args: str, env: dict, cwd: str | Path | None = None,
              input_text: str | None = None) -> subprocess.CompletedProcess:
    """Run a binex CLI command as a real subprocess."""
    return subprocess.run(
        ["binex", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        input=input_text,
        timeout=30,
    )


def write_workflow(tmp_path: Path, name: str, content: str) -> Path:
    """Write a workflow YAML file and return its path."""
    path = tmp_path / f"{name}.yaml"
    path.write_text(content)
    return path


def extract_run_id(output: str) -> str:
    """Extract run_id from binex CLI output (text or JSON)."""
    import json
    # Try JSON first
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line if line.endswith("}") else output[output.index("{"):])
                if "run_id" in data:
                    return data["run_id"]
            except (json.JSONDecodeError, ValueError):
                pass
    # Try text output: "Run ID: run_xxxx"
    for line in output.split("\n"):
        if "Run ID:" in line:
            return line.split("Run ID:")[-1].strip()
    raise ValueError(f"No run_id found in output:\n{output}")
