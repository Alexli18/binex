"""SQLite execution store backend using aiosqlite."""

from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus


class SqliteExecutionStore:
    """SQLite-backed execution store."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                total_nodes INTEGER NOT NULL,
                completed_nodes INTEGER DEFAULT 0,
                failed_nodes INTEGER DEFAULT 0,
                forked_from TEXT,
                forked_at_step TEXT
            );
            CREATE TABLE IF NOT EXISTS execution_records (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                parent_task_id TEXT,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input_artifact_refs TEXT DEFAULT '[]',
                output_artifact_refs TEXT DEFAULT '[]',
                prompt TEXT,
                model TEXT,
                tool_calls TEXT,
                latency_ms INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                error TEXT
            );
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def create_run(self, run_summary: RunSummary) -> None:
        assert self._db is not None
        await self._db.execute(
            """INSERT INTO runs (run_id, workflow_name, status, started_at,
               completed_at, total_nodes, completed_nodes, failed_nodes,
               forked_from, forked_at_step)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_summary.run_id,
                run_summary.workflow_name,
                run_summary.status,
                run_summary.started_at.isoformat(),
                run_summary.completed_at.isoformat() if run_summary.completed_at else None,
                run_summary.total_nodes,
                run_summary.completed_nodes,
                run_summary.failed_nodes,
                run_summary.forked_from,
                run_summary.forked_at_step,
            ),
        )
        await self._db.commit()

    async def get_run(self, run_id: str) -> RunSummary | None:
        assert self._db is not None
        cursor = await self._db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run_summary(row)

    async def update_run(self, run_summary: RunSummary) -> None:
        assert self._db is not None
        await self._db.execute(
            """UPDATE runs SET workflow_name=?, status=?, started_at=?,
               completed_at=?, total_nodes=?, completed_nodes=?, failed_nodes=?,
               forked_from=?, forked_at_step=? WHERE run_id=?""",
            (
                run_summary.workflow_name,
                run_summary.status,
                run_summary.started_at.isoformat(),
                run_summary.completed_at.isoformat() if run_summary.completed_at else None,
                run_summary.total_nodes,
                run_summary.completed_nodes,
                run_summary.failed_nodes,
                run_summary.forked_from,
                run_summary.forked_at_step,
                run_summary.run_id,
            ),
        )
        await self._db.commit()

    async def list_runs(self) -> list[RunSummary]:
        assert self._db is not None
        cursor = await self._db.execute("SELECT * FROM runs")
        rows = await cursor.fetchall()
        return [self._row_to_run_summary(row) for row in rows]

    async def record(self, execution_record: ExecutionRecord) -> None:
        assert self._db is not None
        await self._db.execute(
            """INSERT INTO execution_records (id, run_id, task_id, parent_task_id,
               agent_id, status, input_artifact_refs, output_artifact_refs,
               prompt, model, tool_calls, latency_ms, timestamp, trace_id, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                execution_record.id,
                execution_record.run_id,
                execution_record.task_id,
                execution_record.parent_task_id,
                execution_record.agent_id,
                execution_record.status.value,
                json.dumps(execution_record.input_artifact_refs),
                json.dumps(execution_record.output_artifact_refs),
                execution_record.prompt,
                execution_record.model,
                json.dumps(execution_record.tool_calls) if execution_record.tool_calls else None,
                execution_record.latency_ms,
                execution_record.timestamp.isoformat(),
                execution_record.trace_id,
                execution_record.error,
            ),
        )
        await self._db.commit()

    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM execution_records WHERE run_id = ? AND task_id = ?",
            (run_id, task_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_execution_record(row)

    async def list_records(self, run_id: str) -> list[ExecutionRecord]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM execution_records WHERE run_id = ?", (run_id,)
        )
        rows = await cursor.fetchall()
        return [self._row_to_execution_record(row) for row in rows]

    @staticmethod
    def _row_to_run_summary(row: tuple) -> RunSummary:  # type: ignore[type-arg]
        return RunSummary(
            run_id=row[0],
            workflow_name=row[1],
            status=row[2],
            started_at=datetime.fromisoformat(row[3]),
            completed_at=datetime.fromisoformat(row[4]) if row[4] else None,
            total_nodes=row[5],
            completed_nodes=row[6],
            failed_nodes=row[7],
            forked_from=row[8],
            forked_at_step=row[9],
        )

    @staticmethod
    def _row_to_execution_record(row: tuple) -> ExecutionRecord:  # type: ignore[type-arg]
        return ExecutionRecord(
            id=row[0],
            run_id=row[1],
            task_id=row[2],
            parent_task_id=row[3],
            agent_id=row[4],
            status=TaskStatus(row[5]),
            input_artifact_refs=json.loads(row[6]),
            output_artifact_refs=json.loads(row[7]),
            prompt=row[8],
            model=row[9],
            tool_calls=json.loads(row[10]) if row[10] else None,
            latency_ms=row[11],
            timestamp=datetime.fromisoformat(row[12]),
            trace_id=row[13],
            error=row[14],
        )


__all__ = ["SqliteExecutionStore"]
