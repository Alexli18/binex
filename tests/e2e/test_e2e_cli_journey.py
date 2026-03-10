"""E2E tests: Category 3 — CLI Full Journey.

Real subprocess calls testing the actual CLI interface.
"""

from __future__ import annotations

import json

from .conftest import extract_run_id, run_binex, write_workflow

# --- TC-E2E-016: binex hello full cycle ---

def test_e2e_016_hello_full_cycle(binex_env):
    """`binex hello` runs demo, produces run_id, debuggable afterwards."""
    env, store_path, _ = binex_env

    result = run_binex("hello", env=env)
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "Run completed" in output
    assert "Run ID:" in output

    # Extract run_id and debug it
    run_id = extract_run_id(output)
    debug_result = run_binex("debug", run_id, "--json", env=env)
    assert debug_result.returncode == 0
    data = json.loads(debug_result.stdout)
    assert data["status"] == "completed"
    assert len(data["nodes"]) == 2

    # Real DB created
    assert (store_path / "binex.db").exists()


# --- TC-E2E-017: binex run with --json output ---

def test_e2e_017_run_json_output(binex_env):
    """`binex run --json` produces valid JSON with all expected fields."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "json-test", """
name: e2e-json
nodes:
  producer:
    agent: "local://echo"
    outputs: [result]
  consumer:
    agent: "local://echo"
    outputs: [final]
    depends_on: [producer]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Verify all expected fields
    assert "run_id" in data
    assert "status" in data
    assert data["status"] == "completed"
    assert data["completed_nodes"] == 2
    assert data["total_nodes"] == 2
    assert "output" in data
    assert "workflow_name" in data
    assert data["workflow_name"] == "e2e-json"


# --- TC-E2E-018: binex run with --var substitution ---

def test_e2e_018_run_with_var_substitution(binex_env):
    """`binex run --var` resolves user variables in the workflow."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "var-test", """
name: e2e-var
nodes:
  producer:
    agent: "local://echo"
    inputs:
      topic: "${user.topic}"
    outputs: [result]
""")

    result = run_binex("run", str(wf), "--var", "topic=AI trends", "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "completed"


# --- TC-E2E-019: binex run with --verbose ---

def test_e2e_019_run_verbose(binex_env):
    """`binex run --verbose` shows step-by-step progress."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "verbose-test", """
name: e2e-verbose
nodes:
  producer:
    agent: "local://echo"
    outputs: [result]
  consumer:
    agent: "local://echo"
    outputs: [final]
    depends_on: [producer]
""")

    result = run_binex("run", str(wf), "--verbose", env=env)
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "producer" in output
    assert "consumer" in output
    assert "[1/" in output  # step counter
    assert "[2/" in output


# --- TC-E2E-020: binex validate valid workflow ---

def test_e2e_020_validate_valid_workflow(binex_env):
    """`binex validate` accepts a valid workflow."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "valid", """
name: valid-workflow
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    result = run_binex("validate", str(wf), env=env)
    assert result.returncode == 0


# --- TC-E2E-021: binex validate invalid workflow ---

def test_e2e_021_validate_invalid_workflow(binex_env):
    """`binex validate` rejects a cyclic workflow."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "cyclic", """
name: cyclic-workflow
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
    depends_on: [B]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    result = run_binex("validate", str(wf), env=env)
    assert result.returncode != 0


# --- TC-E2E-022: binex debug with --errors filter ---

def test_e2e_022_debug_errors_filter(binex_env):
    """`binex debug --errors` shows only failed nodes after a failed run."""
    env, _, tmp_path = binex_env

    # Create workflow with a node pointing to unreachable a2a agent
    wf = write_workflow(tmp_path, "debug-err", """
name: e2e-debug-err
nodes:
  ok_node:
    agent: "local://echo"
    outputs: [out]
  fail_node:
    agent: "a2a://localhost:19999"
    outputs: [out]
    depends_on: [ok_node]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 1
    run_id = json.loads(result.stdout)["run_id"]

    # Debug --json shows both nodes
    result = run_binex("debug", run_id, "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "failed"
    assert len(data["nodes"]) == 2

    # Debug --errors shows only failed
    result = run_binex("debug", run_id, "--errors", "--no-rich", env=env)
    assert result.returncode == 0
    assert "fail_node" in result.stdout
