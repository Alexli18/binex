# Stores

## Overview

Stores provide the persistence layer for Binex. Two protocol interfaces define
the contracts: **ExecutionStore** for run metadata and step records, and
**ArtifactStore** for input/output data. The shipped backends are
`SqliteExecutionStore` (SQLite database) and `FilesystemArtifactStore` (JSON
files on disk). In-memory implementations exist for testing.

## Components

| Component               | Module                             | Storage              |
|-------------------------|------------------------------------|----------------------|
| SqliteExecutionStore    | `stores/backends/sqlite.py`        | `.binex/binex.db`    |
| FilesystemArtifactStore | `stores/backends/filesystem.py`    | `.binex/artifacts/`  |
| InMemoryExecutionStore  | `stores/backends/memory.py`        | dict (tests only)    |
| InMemoryArtifactStore   | `stores/backends/memory.py`        | dict (tests only)    |

### Directory layout

```
.binex/
  binex.db                              # SQLite — runs, executions, costs,
                                        #   workflow snapshots
  artifacts/
    {run_id}/
      {artifact_id}.json                # one JSON file per artifact
```

## Interfaces

```python
class ExecutionStore(Protocol):
    async def record(self, execution_record: ExecutionRecord) -> None: ...
    async def get_run(self, run_id: str) -> RunSummary | None: ...
    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None: ...
    async def list_runs(self) -> list[RunSummary]: ...
    async def create_run(self, run_summary: RunSummary) -> None: ...
    async def update_run(self, run_summary: RunSummary) -> None: ...
    async def list_records(self, run_id: str) -> list[ExecutionRecord]: ...
```

```python
class ArtifactStore(Protocol):
    async def store(self, artifact: Artifact) -> None: ...
    async def get(self, artifact_id: str) -> Artifact | None: ...
    async def list_by_run(self, run_id: str) -> list[Artifact]: ...
    async def get_lineage(self, artifact_id: str) -> list[Artifact]: ...
```

```python
class SqliteExecutionStore:
    def __init__(self, db_path: str) -> None: ...
    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
    async def store_workflow_snapshot(self, content: str, version: int) -> str: ...
    async def get_workflow_snapshot(self, hash: str) -> dict | None: ...

class FilesystemArtifactStore:
    def __init__(self, base_path: str) -> None: ...
```

**Important:** `SqliteExecutionStore` uses lazy initialization. Callers must
call `await store.close()` when done to avoid aiosqlite connection hangs.
`FilesystemArtifactStore.get()` scans the filesystem via `rglob` -- it does not
maintain an in-memory index.

## Data Flow

```
Orchestrator
    |
    |--- record step -----> ExecutionStore.record(ExecutionRecord)
    |                              |
    |                              v
    |                        SqliteExecutionStore
    |                              |
    |                              v
    |                        INSERT INTO executions (binex.db)
    |
    |--- store output ----> ArtifactStore.store(Artifact)
    |                              |
    |                              v
    |                        FilesystemArtifactStore
    |                              |
    |                              v
    |                        write .binex/artifacts/{run_id}/{id}.json
    |
    |--- replay / inspect
    |       |
    |       +--- get_run(run_id) -------> SELECT FROM runs
    |       +--- list_records(run_id) --> SELECT FROM executions
    |       +--- get(artifact_id) ------> rglob("{id}.json")
    |       +--- get_lineage(id) -------> walk parent_id chain
    |
    |--- snapshot workflow --> store_workflow_snapshot(yaml, version)
    |                              |
    |                              v
    |                        SHA256 hash → deduplicated INSERT
    |                        INTO workflow_snapshots (binex.db)
    |
    |--- diff workflows ----> get_workflow_snapshot(hash)
    |                              |
    |                              v
    |                        SELECT FROM workflow_snapshots
    v
```

## SQLite Schema

### `runs` table

| Column | Type | Description |
|--------|------|-------------|
| `run_id` | TEXT PK | Unique run identifier |
| `workflow_name` | TEXT | Workflow name from spec |
| `status` | TEXT | Run status (`completed`, `failed`, `over_budget`, ...) |
| `started_at` | TEXT | ISO 8601 start timestamp |
| `completed_at` | TEXT | ISO 8601 completion timestamp |
| `total_nodes` | INT | Total node count |
| `completed_nodes` | INT | Successfully completed nodes |
| `failed_nodes` | INT | Failed node count |
| `skipped_nodes` | INT | Skipped node count |
| `forked_from` | TEXT | Parent run ID (for replays) |
| `forked_at_step` | TEXT | Fork point step ID |
| `workflow_hash` | TEXT | SHA256 hash linking to `workflow_snapshots` |
| `total_cost` | REAL | Accumulated cost |

### `workflow_snapshots` table

Added in v0.4.0. Stores deduplicated workflow definitions for run reproducibility.

| Column | Type | Description |
|--------|------|-------------|
| `hash` | TEXT PK | SHA256 of normalized YAML content |
| `content` | TEXT | Normalized YAML (sorted keys, no `source_path`) |
| `version` | INT | Schema version at time of snapshot |
| `created_at` | TEXT | ISO 8601 timestamp of first storage |

Snapshots are **deduplicated by hash** — identical workflows share a single row regardless of how many runs use them. The `workflow_hash` column in `runs` is a foreign key reference.

### Snapshot workflow

1. Orchestrator normalizes `WorkflowSpec` → `yaml.dump(sort_keys=True)`, excluding `source_path`
2. `store_workflow_snapshot(content, version)` computes SHA256, inserts if new, returns hash
3. Hash is stored on `RunSummary.workflow_hash` and persisted in the `runs` table
4. `binex workflow diff <run1> <run2>` retrieves snapshots by hash and shows unified diff
