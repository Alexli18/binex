"""E2E tests: Category 5 — Data Integrity.

Real subprocess calls. Verifies real SQLite data and filesystem artifacts.
"""

from __future__ import annotations

import json
import sqlite3

from .conftest import run_binex, write_workflow

# --- TC-E2E-029: SQLite database has correct schema ---

def test_e2e_029_sqlite_schema(binex_env):
    """After a run, SQLite DB has runs, execution_records, and cost_records tables."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "schema", """
name: e2e-schema
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0

    # Inspect real SQLite DB
    db_path = store_path / "binex.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "runs" in tables
    assert "execution_records" in tables
    assert "cost_records" in tables

    conn.close()


# --- TC-E2E-030: Run data persists in SQLite ---

def test_e2e_030_run_data_in_sqlite(binex_env):
    """Run summary is correctly persisted in SQLite."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "persist", """
name: e2e-persist
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    run_id = json.loads(result.stdout)["run_id"]

    # Query SQLite directly
    db_path = store_path / "binex.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    assert row is not None
    assert row["status"] == "completed"
    assert row["workflow_name"] == "e2e-persist"
    assert row["total_nodes"] == 2
    assert row["completed_nodes"] == 2
    assert row["failed_nodes"] == 0

    conn.close()


# --- TC-E2E-031: Execution records match nodes ---

def test_e2e_031_execution_records_match(binex_env):
    """Execution records in SQLite match the workflow nodes."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "records", """
name: e2e-records
nodes:
  n1:
    agent: "local://echo"
    outputs: [out]
  n2:
    agent: "local://echo"
    outputs: [out]
    depends_on: [n1]
  n3:
    agent: "local://echo"
    outputs: [out]
    depends_on: [n2]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    run_id = json.loads(result.stdout)["run_id"]

    db_path = store_path / "binex.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        "SELECT task_id, status FROM execution_records WHERE run_id = ?",
        (run_id,),
    )
    rows = cursor.fetchall()
    assert len(rows) == 3
    task_ids = {row[0] for row in rows}
    assert task_ids == {"n1", "n2", "n3"}
    assert all(row[1] == "completed" for row in rows)

    conn.close()


# --- TC-E2E-032: Cost records in SQLite ---

def test_e2e_032_cost_records_in_sqlite(binex_env):
    """Cost records persist correctly in SQLite with all fields."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "costdb", """
name: e2e-costdb
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0
    run_id = json.loads(result.stdout)["run_id"]

    db_path = store_path / "binex.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Local adapters no longer create cost records
    cursor.execute("SELECT * FROM cost_records WHERE run_id = ?", (run_id,))
    rows = cursor.fetchall()
    assert len(rows) == 0

    conn.close()


# --- TC-E2E-033: Artifact files on disk ---

def test_e2e_033_artifact_files_on_disk(binex_env):
    """Artifacts are stored as real JSON files on the filesystem."""
    env, store_path, tmp_path = binex_env

    wf = write_workflow(tmp_path, "artfiles", """
name: e2e-artfiles
nodes:
  A:
    agent: "local://echo"
    outputs: [out]
  B:
    agent: "local://echo"
    outputs: [out]
    depends_on: [A]
""")

    result = run_binex("run", str(wf), "--json", env=env)
    assert result.returncode == 0

    # Check artifact files exist
    artifacts_dir = store_path / "artifacts"
    assert artifacts_dir.exists()

    artifact_files = list(artifacts_dir.rglob("*.json"))
    assert len(artifact_files) >= 2

    # Each artifact file is valid JSON with expected fields
    for f in artifact_files:
        data = json.loads(f.read_text())
        assert "id" in data
        assert "run_id" in data
        assert "type" in data
        assert "content" in data
        assert "lineage" in data
        assert "produced_by" in data["lineage"]
