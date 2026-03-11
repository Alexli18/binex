"""SQLite execution store backend using aiosqlite."""

from __future__ import annotations

import json
from datetime import datetime

import aiosqlite

from binex.models.cost import CostRecord, RunCostSummary
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus


class SqliteExecutionStore:
    """SQLite-backed execution store."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._initialized = False

    async def _ensure_initialized(self) -> aiosqlite.Connection:
        if not self._initialized:
            await self.initialize()
        assert self._db is not None
        return self._db

    async def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
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
                forked_at_step TEXT,
                total_cost REAL DEFAULT 0.0,
                workflow_path TEXT
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
            CREATE TABLE IF NOT EXISTS cost_records (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                cost REAL NOT NULL DEFAULT 0.0,
                currency TEXT NOT NULL DEFAULT 'USD',
                source TEXT NOT NULL,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                model TEXT,
                timestamp TEXT NOT NULL
            );
        """)
        # Migration: add total_cost column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN total_cost REAL DEFAULT 0.0")
            await self._db.commit()
        except Exception:
            pass  # Column already exists
        # Migration: add workflow_path column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN workflow_path TEXT")
            await self._db.commit()
        except Exception:
            pass  # Column already exists
        await self._db.commit()
        self._initialized = True

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
            self._initialized = False

    async def create_run(self, run_summary: RunSummary) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            """INSERT INTO runs (run_id, workflow_name, status, started_at,
               completed_at, total_nodes, completed_nodes, failed_nodes,
               forked_from, forked_at_step, total_cost, workflow_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                run_summary.total_cost,
                run_summary.workflow_path,
            ),
        )
        await db.commit()

    async def get_run(self, run_id: str) -> RunSummary | None:
        db = await self._ensure_initialized()
        cursor = await db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run_summary(row)

    async def update_run(self, run_summary: RunSummary) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            """UPDATE runs SET workflow_name=?, status=?, started_at=?,
               completed_at=?, total_nodes=?, completed_nodes=?, failed_nodes=?,
               forked_from=?, forked_at_step=?, total_cost=?, workflow_path=?
               WHERE run_id=?""",
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
                run_summary.total_cost,
                run_summary.workflow_path,
                run_summary.run_id,
            ),
        )
        await db.commit()

    async def list_runs(self) -> list[RunSummary]:
        db = await self._ensure_initialized()
        cursor = await db.execute("SELECT * FROM runs")
        rows = await cursor.fetchall()
        return [self._row_to_run_summary(row) for row in rows]

    async def record(self, execution_record: ExecutionRecord) -> None:
        db = await self._ensure_initialized()
        await db.execute(
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
        await db.commit()

    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None:
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT * FROM execution_records WHERE run_id = ? AND task_id = ?",
            (run_id, task_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_execution_record(row)

    async def list_records(self, run_id: str) -> list[ExecutionRecord]:
        db = await self._ensure_initialized()
        cursor = await db.execute(
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
            total_cost=row[10] if len(row) > 10 else 0.0,
            workflow_path=row[11] if len(row) > 11 else None,
        )

    async def record_cost(self, cost_record: CostRecord) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            """INSERT INTO cost_records (id, run_id, task_id, cost, currency,
               source, prompt_tokens, completion_tokens, model, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cost_record.id,
                cost_record.run_id,
                cost_record.task_id,
                cost_record.cost,
                cost_record.currency,
                cost_record.source,
                cost_record.prompt_tokens,
                cost_record.completion_tokens,
                cost_record.model,
                cost_record.timestamp.isoformat(),
            ),
        )
        await db.commit()

    async def list_costs(self, run_id: str) -> list[CostRecord]:
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT * FROM cost_records WHERE run_id = ? ORDER BY timestamp",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_cost_record(row) for row in rows]

    async def get_run_cost_summary(self, run_id: str) -> RunCostSummary:
        records = await self.list_costs(run_id)
        total_cost = sum(r.cost for r in records)
        node_costs: dict[str, float] = {}
        for r in records:
            node_costs[r.task_id] = node_costs.get(r.task_id, 0.0) + r.cost
        return RunCostSummary(
            run_id=run_id,
            total_cost=total_cost,
            node_costs=node_costs,
        )

    @staticmethod
    def _row_to_cost_record(row: tuple) -> CostRecord:  # type: ignore[type-arg]
        return CostRecord(
            id=row[0],
            run_id=row[1],
            task_id=row[2],
            cost=row[3],
            currency=row[4],
            source=row[5],
            prompt_tokens=row[6],
            completion_tokens=row[7],
            model=row[8],
            timestamp=datetime.fromisoformat(row[9]),
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
