"""E2E tests: Category 4 — Error Handling & Edge Cases.

Real subprocess calls. Tests failures, validation errors, edge cases.
"""

from __future__ import annotations

import json

from .conftest import run_binex, write_workflow

# --- TC-E2E-023: Run with invalid YAML ---

def test_e2e_023_invalid_yaml(binex_env):
    """Invalid YAML file produces a clear error."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "invalid", """
name: bad-workflow
nodes:
  A:
    agent: "local://echo"
    - this is not valid yaml
""")

    result = run_binex("run", str(wf), env=env)
    assert result.returncode != 0


# --- TC-E2E-024: Run nonexistent file ---

def test_e2e_024_nonexistent_file(binex_env):
    """Running a nonexistent workflow file produces error."""
    env, _, _ = binex_env

    result = run_binex("run", "/tmp/nonexistent_workflow_12345.yaml", env=env)
    assert result.returncode != 0


# --- TC-E2E-025: Debug nonexistent run ---

def test_e2e_025_debug_nonexistent_run(binex_env):
    """Debugging a nonexistent run_id produces error."""
    env, _, _ = binex_env

    result = run_binex("debug", "run_does_not_exist", env=env)
    assert result.returncode != 0
    assert "not found" in result.stderr.lower()


# --- TC-E2E-026: Debug with 'latest' ---

def test_e2e_026_debug_latest(binex_env):
    """`binex debug latest` resolves to the most recent run."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "latest", """
name: e2e-latest
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
""")

    # Run a workflow first
    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    expected_id = json.loads(result.stdout)["run_id"]

    # Debug latest
    result = run_binex("debug", "latest", "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["run_id"] == expected_id


# --- TC-E2E-027: Validate with --json ---

def test_e2e_027_validate_json_output(binex_env):
    """`binex validate --json` produces structured validation output."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "valjson", """
name: val-json
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    result = run_binex("validate", str(wf), "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "valid" in data or "nodes" in data


# --- TC-E2E-028: Cancel nonexistent run ---

def test_e2e_028_cancel_nonexistent(binex_env):
    """Cancelling a nonexistent run returns error."""
    env, _, _ = binex_env

    result = run_binex("cancel", "run_nonexistent_123", env=env)
    assert result.returncode != 0
    assert "not found" in result.stderr.lower()
