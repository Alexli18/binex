"""E2E tests: Category 1 — Complete Workflow Lifecycle.

Real subprocess calls, real SQLite, real filesystem artifacts.
No mocks. Tests full user journey: run -> debug -> cost -> replay.
"""

from __future__ import annotations

import json

from .conftest import run_binex, write_workflow

# --- TC-E2E-001: Simple 2-node pipeline: run -> debug -> cost ---

def test_e2e_001_simple_pipeline_full_cycle(binex_env):
    """Run a simple pipeline, then debug and cost inspect via real CLI."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "simple", """
name: e2e-simple
nodes:
  producer:
    agent: "local://echo"
    outputs: [result]
  consumer:
    agent: "local://echo"
    outputs: [final]
    depends_on: [producer]
""")

    # Step 1: Run workflow
    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "completed"
    assert data["completed_nodes"] == 2
    assert data["total_nodes"] == 2
    run_id = data["run_id"]

    # Step 2: Debug the run
    result = run_binex("debug", run_id, "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    debug_data = json.loads(result.stdout)
    assert debug_data["run_id"] == run_id
    assert debug_data["status"] == "completed"
    assert len(debug_data["nodes"]) == 2

    # Step 3: Cost show
    result = run_binex("cost", "show", run_id, "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    cost_data = json.loads(result.stdout)
    assert cost_data["run_id"] == run_id
    assert cost_data["total_cost"] == 0.0  # local adapters = $0

    # Step 4: Cost history
    result = run_binex("cost", "history", run_id, "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    hist_data = json.loads(result.stdout)
    assert hist_data["run_id"] == run_id
    assert len(hist_data["records"]) == 2  # one per node

    # Step 5: Verify real files on disk
    db_file = store_path / "binex.db"
    assert db_file.exists()
    assert db_file.stat().st_size > 0

    artifacts_dir = store_path / "artifacts"
    assert artifacts_dir.exists()
    artifact_files = list(artifacts_dir.rglob("*.json"))
    assert len(artifact_files) >= 2


# --- TC-E2E-002: 5-node fan-out/fan-in pipeline ---

def test_e2e_002_fanout_fanin_pipeline(binex_env):
    """5-node fan-out/fan-in pattern — real execution."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "fanout", """
name: e2e-fanout
nodes:
  planner:
    agent: "local://echo"
    outputs: [plan]
  r1:
    agent: "local://echo"
    outputs: [data]
    depends_on: [planner]
  r2:
    agent: "local://echo"
    outputs: [data]
    depends_on: [planner]
  r3:
    agent: "local://echo"
    outputs: [data]
    depends_on: [planner]
  aggregator:
    agent: "local://echo"
    outputs: [summary]
    depends_on: [r1, r2, r3]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "completed"
    assert data["completed_nodes"] == 5
    assert data["total_nodes"] == 5


# --- TC-E2E-003: Diamond DAG ---

def test_e2e_003_diamond_dag(binex_env):
    """Diamond DAG (A -> B, C -> D) — real execution."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "diamond", """
name: e2e-diamond
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
  C:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
  D:
    agent: "local://echo"
    outputs: [out]
    depends_on: [B, C]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "completed"
    assert data["completed_nodes"] == 4


# --- TC-E2E-004: Workflow with failing node ---

def test_e2e_004_workflow_with_failing_node(binex_env):
    """Workflow referencing unregistered a2a agent fails gracefully."""
    env, _, tmp_path = binex_env

    # Use an a2a:// agent pointing to non-existent server — will fail on connect
    wf = write_workflow(tmp_path, "fail", """
name: e2e-fail
nodes:
  producer:
    agent: "local://echo"
    outputs: [result]
  consumer:
    agent: "a2a://localhost:19999"
    outputs: [final]
    depends_on: [producer]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 1  # failed run
    data = json.loads(result.stdout)
    assert data["status"] == "failed"
    assert data["failed_nodes"] >= 1

    # Debug should show the error
    run_id = data["run_id"]
    debug_result = run_binex("debug", run_id, "--json", env=env)
    assert debug_result.returncode == 0
    debug_data = json.loads(debug_result.stdout)
    failed_nodes = [n for n in debug_data["nodes"] if n["status"] == "failed"]
    assert len(failed_nodes) >= 1
    assert failed_nodes[0]["error"] is not None


# --- TC-E2E-005 & 006: Conditional execution (human-in-the-loop simulation) ---
# Note: Real human:// adapters need interactive input.
# We test conditional routing via local adapters that produce "decision" artifacts.
# The when-condition evaluation is tested through validate + the existing
# integration test in test_orchestrator.py. For real E2E, we verify
# the workflow file loads and validates.


# --- TC-E2E-007: Replay from mid-pipeline step ---

def test_e2e_007_replay_from_midpipeline(binex_env):
    """Replay a run from step B — real CLI, real stores."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "replay", """
name: e2e-replay
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
  C:
    agent: "local://echo"
    outputs: [out]
    depends_on: [B]
""")

    # Step 1: Run original
    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    original_data = json.loads(result.stdout)
    original_run_id = original_data["run_id"]
    assert original_data["status"] == "completed"

    # Step 2: Replay from B
    result = run_binex(
        "replay", original_run_id,
        "--from", "B",
        "--workflow", str(wf),
        "--json",
        env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    replay_data = json.loads(result.stdout)
    assert replay_data["status"] == "completed"
    assert replay_data["forked_from"] == original_run_id
    assert replay_data["forked_at_step"] == "B"
    assert replay_data["run_id"] != original_run_id

    # Step 3: Both runs visible in debug
    for rid in [original_run_id, replay_data["run_id"]]:
        r = run_binex("debug", rid, "--json", env=env)
        assert r.returncode == 0


# --- TC-E2E-008: Replay with agent swap ---

def test_e2e_008_replay_with_agent_swap(binex_env):
    """Replay with --agent swap — real CLI."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "swap", """
name: e2e-swap
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    # Run original
    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    run_id = json.loads(result.stdout)["run_id"]

    # Replay with agent swap (both are local, but verifies the mechanism)
    result = run_binex(
        "replay", run_id,
        "--from", "B",
        "--workflow", str(wf),
        "--agent", "B=local://echo",
        "--json",
        env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    data = json.loads(result.stdout)
    assert data["status"] == "completed"
    assert data["forked_from"] == run_id
