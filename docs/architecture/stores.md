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
  binex.db                              # SQLite — runs + execution records
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
    v
```
