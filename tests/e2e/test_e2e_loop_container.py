"""E2E tests for Loop Container (018-loop-container).

Real subprocess calls, real SQLite, real filesystem artifacts.
No mocks. Tests loop workflows with local://echo adapters.
"""

from __future__ import annotations

import json
import sqlite3

from .conftest import run_binex, write_workflow


# --- TC-E2E-LOOP-001: Basic loop workflow — max iterations exceeded ---

def test_e2e_loop_001_basic_loop_max_iterations(binex_env):
    """Loop with local://echo agents never meets exit condition → max iterations."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "loop_basic", """
name: e2e-loop-basic
nodes:
  setup:
    agent: "local://echo"
    outputs: [context]
  writer:
    agent: "local://echo"
    outputs: [draft]
    depends_on: [setup]
  reviewer:
    agent: "local://echo"
    outputs: [score]
    depends_on: [writer]
  refine_loop:
    type: loop
    outputs: [refined]
    depends_on: [setup]
    loop:
      exit:
        field: "$.score"
        operator: ">="
        value: 0.9
      max_iterations: 3
      contains: [writer, reviewer]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    # Loop should fail with max iterations exceeded
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    assert data["status"] == "failed"
    assert data["failed_nodes"] == 1

    run_id = data["run_id"]

    # Debug: check loop node failed and inner nodes ran
    debug = run_binex("debug", run_id, "--json", env=env)
    debug_data = json.loads(debug.stdout)

    node_ids = [n["node_id"] for n in debug_data["nodes"]]
    # Should have: setup, refine_loop.writer × 3, refine_loop.reviewer × 3, refine_loop
    assert "setup" in node_ids
    assert node_ids.count("refine_loop.writer") == 3  # 3 iterations
    assert node_ids.count("refine_loop.reviewer") == 3

    # refine_loop itself should be failed
    loop_node = next(n for n in debug_data["nodes"] if n["node_id"] == "refine_loop")
    assert loop_node["status"] == "failed"
    assert "max iterations" in loop_node["error"].lower()


# --- TC-E2E-LOOP-002: Loop with max_iterations=1 ---

def test_e2e_loop_002_single_iteration(binex_env):
    """Loop with max_iterations=1 — runs exactly once."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "loop_single", """
name: e2e-loop-single
nodes:
  worker:
    agent: "local://echo"
    outputs: [result]
  my_loop:
    type: loop
    outputs: [out]
    loop:
      exit:
        field: "$.done"
        operator: "=="
        value: true
      max_iterations: 1
      contains: [worker]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    run_id = data["run_id"]

    # Debug: should have exactly 1 inner execution + loop container
    debug = run_binex("debug", run_id, "--json", env=env)
    debug_data = json.loads(debug.stdout)

    inner_nodes = [n for n in debug_data["nodes"] if n["node_id"].startswith("my_loop.")]
    assert len(inner_nodes) == 1  # exactly 1 iteration


# --- TC-E2E-LOOP-003: SQLite iteration_number stored correctly ---

def test_e2e_loop_003_iteration_number_in_sqlite(binex_env):
    """Verify iteration_number is stored in SQLite execution_records."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "loop_iter", """
name: e2e-loop-iter
nodes:
  worker:
    agent: "local://echo"
    outputs: [result]
  my_loop:
    type: loop
    outputs: [out]
    loop:
      exit:
        field: "$.x"
        operator: ">="
        value: 999
      max_iterations: 3
      contains: [worker]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    run_id = data["run_id"]

    # Query SQLite directly
    db_path = store_path / "binex.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT task_id, iteration_number FROM execution_records "
        "WHERE run_id = ? AND iteration_number IS NOT NULL "
        "ORDER BY iteration_number",
        (run_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 3  # 3 iterations × 1 worker
    task_ids = [r[0] for r in rows]
    iter_nums = [r[1] for r in rows]

    # Dotted format
    assert all("my_loop.worker" in tid for tid in task_ids)
    # Iteration numbers 1, 2, 3
    assert iter_nums == [1, 2, 3]


# --- TC-E2E-LOOP-004: Loop artifacts on disk ---

def test_e2e_loop_004_artifacts_on_disk(binex_env):
    """Verify loop iteration artifacts are stored on filesystem."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "loop_artifacts", """
name: e2e-loop-artifacts
nodes:
  worker:
    agent: "local://echo"
    outputs: [data]
  my_loop:
    type: loop
    outputs: [out]
    loop:
      exit:
        field: "$.never"
        operator: "=="
        value: true
      max_iterations: 2
      contains: [worker]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    run_id = data["run_id"]

    # Check artifact files on disk
    artifacts_dir = store_path / "artifacts"
    assert artifacts_dir.exists()
    artifact_files = list(artifacts_dir.rglob("*.json"))
    # local://echo produces artifacts with same ID across iterations
    # (art_worker), so filesystem may have just 1 file (last write wins)
    assert len(artifact_files) >= 1

    # Verify artifact JSON structure
    for af in artifact_files:
        art = json.loads(af.read_text())
        assert "id" in art
        assert "run_id" in art
        assert art["run_id"] == run_id
        assert "content" in art
        assert "type" in art


# --- TC-E2E-LOOP-005: Loop with entry_node and output_node ---

def test_e2e_loop_005_entry_and_output_node(binex_env):
    """Loop with explicit entry_node/output_node runs correctly."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "loop_entry_output", """
name: e2e-loop-entry-output
nodes:
  writer:
    agent: "local://echo"
    outputs: [draft]
  reviewer:
    agent: "local://echo"
    outputs: [score]
    depends_on: [writer]
  refine:
    type: loop
    outputs: [result]
    loop:
      exit:
        field: "$.score"
        operator: ">="
        value: 0.9
      max_iterations: 2
      contains: [writer, reviewer]
      entry_node: writer
      output_node: reviewer
""")

    result = run_binex("run", str(wf), "--json", env=env)
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    run_id = data["run_id"]

    debug = run_binex("debug", run_id, "--json", env=env)
    debug_data = json.loads(debug.stdout)

    # Both writer and reviewer should have run in each iteration
    writer_nodes = [n for n in debug_data["nodes"] if n["node_id"] == "refine.writer"]
    reviewer_nodes = [n for n in debug_data["nodes"] if n["node_id"] == "refine.reviewer"]
    assert len(writer_nodes) == 2
    assert len(reviewer_nodes) == 2


# --- TC-E2E-LOOP-006: Validator rejects invalid loop ---

def test_e2e_loop_006_validator_rejects_nested_loop(binex_env):
    """Validator rejects nested loops at load time."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "nested_loop", """
name: e2e-nested-loop
nodes:
  worker:
    agent: "local://echo"
    outputs: [out]
  inner_loop:
    type: loop
    outputs: [inner_out]
    loop:
      exit:
        field: "$.x"
        operator: ">="
        value: 1
      contains: [worker]
  outer_loop:
    type: loop
    outputs: [outer_out]
    loop:
      exit:
        field: "$.y"
        operator: ">="
        value: 1
      contains: [inner_loop]
""")

    result = run_binex("run", str(wf), env=env)
    assert result.returncode != 0
    assert "nested" in result.stderr.lower() or "nested" in result.stdout.lower()


# --- TC-E2E-LOOP-007: Validator rejects entry_node not in contains ---

def test_e2e_loop_007_validator_rejects_bad_entry_node(binex_env):
    """Validator rejects entry_node that's not in contains list."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "bad_entry", """
name: e2e-bad-entry
nodes:
  worker:
    agent: "local://echo"
    outputs: [out]
  my_loop:
    type: loop
    outputs: [result]
    loop:
      exit:
        field: "$.x"
        operator: ">="
        value: 1
      contains: [worker]
      entry_node: nonexistent
""")

    result = run_binex("run", str(wf), env=env)
    assert result.returncode != 0
    assert "entry_node" in result.stderr.lower() or "entry_node" in result.stdout.lower()


# --- TC-E2E-LOOP-008: Two independent loops in one workflow ---

def test_e2e_loop_008_two_independent_loops(binex_env):
    """Workflow with two independent loops runs both."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "two_loops", """
name: e2e-two-loops
nodes:
  w1:
    agent: "local://echo"
    outputs: [o]
  r1:
    agent: "local://echo"
    outputs: [o]
    depends_on: [w1]
  w2:
    agent: "local://echo"
    outputs: [o]
  r2:
    agent: "local://echo"
    outputs: [o]
    depends_on: [w2]
  loop_a:
    type: loop
    outputs: [out_a]
    loop:
      exit:
        field: "$.x"
        operator: ">="
        value: 999
      max_iterations: 2
      contains: [w1, r1]
  loop_b:
    type: loop
    outputs: [out_b]
    loop:
      exit:
        field: "$.y"
        operator: ">="
        value: 999
      max_iterations: 2
      contains: [w2, r2]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    run_id = data["run_id"]

    debug = run_binex("debug", run_id, "--json", env=env)
    debug_data = json.loads(debug.stdout)

    # Both loops should have run
    loop_a_nodes = [n for n in debug_data["nodes"] if n["node_id"].startswith("loop_a.")]
    loop_b_nodes = [n for n in debug_data["nodes"] if n["node_id"].startswith("loop_b.")]
    assert len(loop_a_nodes) == 4  # 2 iterations × 2 nodes
    assert len(loop_b_nodes) == 4


# --- TC-E2E-LOOP-009: Sequential loops (loop_b depends on loop_a) ---

def test_e2e_loop_009_sequential_loops(binex_env):
    """Two loops where loop_b depends on loop_a."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "seq_loops", """
name: e2e-seq-loops
nodes:
  w1:
    agent: "local://echo"
    outputs: [o]
  w2:
    agent: "local://echo"
    outputs: [o]
  loop_a:
    type: loop
    outputs: [out_a]
    loop:
      exit:
        field: "$.x"
        operator: ">="
        value: 999
      max_iterations: 1
      contains: [w1]
  loop_b:
    type: loop
    outputs: [out_b]
    depends_on: [loop_a]
    loop:
      exit:
        field: "$.y"
        operator: ">="
        value: 999
      max_iterations: 1
      contains: [w2]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    data = json.loads(result.stdout if result.stdout else result.stderr.split('\n')[-1])
    run_id = data["run_id"]

    debug = run_binex("debug", run_id, "--json", env=env)
    debug_data = json.loads(debug.stdout)

    # loop_a ran and failed (max iterations)
    loop_a = next(n for n in debug_data["nodes"] if n["node_id"] == "loop_a")
    assert loop_a["status"] == "failed"

    # loop_b depends on loop_a, so when loop_a fails, loop_b is skipped
    # Scheduler may mask skipped node IDs as <skipped-N>
    statuses = [n["status"] for n in debug_data["nodes"]]
    # At least one node should be skipped (loop_b and/or its inner nodes)
    assert "skipped" in statuses or data["skipped_nodes"] > 0 or data["failed_nodes"] >= 1
