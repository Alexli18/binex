"""E2E tests: Category 2 — Budget & Cost Tracking.

Real subprocess calls. Local adapters cost $0, so budget tests focus
on the budget enforcement mechanism (not actual LLM costs).
"""

from __future__ import annotations

import json

from .conftest import run_binex, write_workflow

# --- TC-E2E-009: Cost tracking with local adapters ---

def test_e2e_009_cost_records_created(binex_env):
    """Cost records exist for every node after a real run."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "cost", """
name: e2e-cost
nodes:
  step_a:
    agent: "local://echo"
    outputs: [out]
  step_b:
    agent: "local://echo"
    outputs: [out]
    depends_on: [step_a]
  step_c:
    agent: "local://echo"
    outputs: [out]
    depends_on: [step_b]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    run_data = json.loads(result.stdout)
    run_id = run_data["run_id"]

    # Cost show
    result = run_binex("cost", "show", run_id, "--json", env=env)
    assert result.returncode == 0
    cost_data = json.loads(result.stdout)
    assert cost_data["total_cost"] == 0.0
    assert len(cost_data["nodes"]) == 3

    # Cost history
    result = run_binex("cost", "history", run_id, "--json", env=env)
    assert result.returncode == 0
    hist = json.loads(result.stdout)
    assert len(hist["records"]) == 3
    assert all(r["source"] == "local" for r in hist["records"])


# --- TC-E2E-010: Budget in JSON output ---

def test_e2e_010_budget_in_json_output(binex_env):
    """Budget info appears in --json output when budget is set."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "budget", """
name: e2e-budget
budget:
  max_cost: 10.0
  policy: warn
nodes:
  step_a:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "completed"
    assert data["budget"] == 10.0
    assert data["remaining_budget"] == 10.0  # local = $0 cost


# --- TC-E2E-011: Budget text output ---

def test_e2e_011_budget_text_output(binex_env):
    """Budget info appears in text output."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "budget-text", """
name: e2e-budget-text
budget:
  max_cost: 5.0
  policy: warn
nodes:
  step_a:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), env=env)
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "Budget:" in output or "$5.00" in output


# --- TC-E2E-012: Cost show text output ---

def test_e2e_012_cost_show_text(binex_env):
    """Cost show text output has readable format."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "cost-text", """
name: e2e-cost-text
nodes:
  node_a:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    run_id = json.loads(result.stdout)["run_id"]

    result = run_binex("cost", "show", run_id, env=env)
    assert result.returncode == 0
    assert f"Run: {run_id}" in result.stdout
    assert "Total cost:" in result.stdout


# --- TC-E2E-013: Cost history text output ---

def test_e2e_013_cost_history_text(binex_env):
    """Cost history text output has readable format."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "cost-hist", """
name: e2e-cost-hist
nodes:
  step_a:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    run_id = json.loads(result.stdout)["run_id"]

    result = run_binex("cost", "history", run_id, env=env)
    assert result.returncode == 0
    assert "Cost history for" in result.stdout
    assert "local" in result.stdout  # source=local


# --- TC-E2E-014: Cost for nonexistent run ---

def test_e2e_014_cost_nonexistent_run(binex_env):
    """Cost commands fail gracefully for nonexistent run_id."""
    env, _, _ = binex_env

    result = run_binex("cost", "show", "run_nonexistent", env=env)
    assert result.returncode != 0
    assert "not found" in result.stderr.lower()

    result = run_binex("cost", "history", "run_nonexistent", env=env)
    assert result.returncode != 0
    assert "not found" in result.stderr.lower()


# --- TC-E2E-015: Multiple runs have isolated cost data ---

def test_e2e_015_multiple_runs_isolated_costs(binex_env):
    """Each run has its own cost records in the same SQLite DB."""
    env, _, tmp_path = binex_env

    wf = write_workflow(tmp_path, "multi", """
name: e2e-multi
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    run_ids = []
    for _ in range(3):
        result = run_binex("run", str(wf), "--json", env=env)
        assert result.returncode == 0
        run_ids.append(json.loads(result.stdout)["run_id"])

    # All run_ids unique
    assert len(set(run_ids)) == 3

    # Each run has exactly 2 cost records
    for rid in run_ids:
        result = run_binex("cost", "history", rid, "--json", env=env)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data["records"]) == 2
