"""SQLite execution store backend using aiosqlite."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from binex.models.cache import CacheEntry
from binex.models.cost import CostRecord, RunCostSummary
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus

logger = logging.getLogger(__name__)


class SqliteExecutionStore:
    """SQLite-backed execution store."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._initialized = False
        # In-memory running totals: invalidated on close/reinit
        self._node_costs: dict[str, dict[str, float]] = {}

    async def _ensure_initialized(self) -> aiosqlite.Connection:
        if not self._initialized:
            await self.initialize()
        assert self._db is not None
        return self._db

    async def initialize(self) -> None:
        import os
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        # WAL lets the Web UI read run data while the orchestrator writes,
        # instead of raising "database is locked" in rollback-journal mode.
        # busy_timeout waits out brief write locks; synchronous=NORMAL is the
        # safe, recommended pairing with WAL.
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA busy_timeout=5000")
        await self._db.execute("PRAGMA synchronous=NORMAL")
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
                skipped_nodes INTEGER DEFAULT 0,
                forked_from TEXT,
                forked_at_step TEXT,
                total_cost REAL DEFAULT 0.0,
                workflow_path TEXT,
                resumed_from TEXT,
                git_sha TEXT,
                git_dirty INTEGER DEFAULT 0,
                observed INTEGER DEFAULT 0
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
                error TEXT,
                trace_events TEXT,
                requested_model TEXT,
                actual_model TEXT
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
                timestamp TEXT NOT NULL,
                unit TEXT DEFAULT 'tokens',
                quantity REAL,
                unit_price REAL,
                provenance TEXT DEFAULT 'litellm'
            );
            CREATE TABLE IF NOT EXISTS cao_sessions (
                terminal_id  TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                node_name    TEXT NOT NULL,
                session_name TEXT,
                started_at   TEXT NOT NULL,
                completed_at TEXT,
                status       TEXT NOT NULL DEFAULT 'active'
            );
            CREATE TABLE IF NOT EXISTS workflow_snapshots (
                hash TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cache_entries (
                cache_key TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                artifact_ids TEXT NOT NULL,
                saved_cost REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_execution_records_run_id
                ON execution_records (run_id);
            CREATE INDEX IF NOT EXISTS idx_execution_records_run_task
                ON execution_records (run_id, task_id);
            CREATE INDEX IF NOT EXISTS idx_cost_records_run_id
                ON cost_records (run_id);
            CREATE INDEX IF NOT EXISTS idx_cost_records_run_task
                ON cost_records (run_id, task_id);
            CREATE INDEX IF NOT EXISTS idx_cost_records_covering
                ON cost_records (run_id, task_id, cost);
            CREATE INDEX IF NOT EXISTS idx_cao_sessions_status
                ON cao_sessions (status);
        """)
        # Migration: add total_cost column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN total_cost REAL DEFAULT 0.0")
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add workflow_path column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN workflow_path TEXT")
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add skipped_nodes column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN skipped_nodes INTEGER DEFAULT 0")
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add workflow_hash column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN workflow_hash TEXT")
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add resumed_from column to existing runs table
        try:
            await self._db.execute("ALTER TABLE runs ADD COLUMN resumed_from TEXT")
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add git provenance columns to existing runs table (#72)
        for _col, _decl in (("git_sha", "TEXT"), ("git_dirty", "INTEGER DEFAULT 0")):
            try:
                await self._db.execute(f"ALTER TABLE runs ADD COLUMN {_col} {_decl}")
                await self._db.commit()
            except Exception as exc:
                logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add observed column to existing runs table (#73)
        try:
            await self._db.execute(
                "ALTER TABLE runs ADD COLUMN observed INTEGER DEFAULT 0"
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add trace_events column to existing execution_records table
        try:
            await self._db.execute(
                "ALTER TABLE execution_records ADD COLUMN trace_events TEXT"
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add requested_model / actual_model (fallback chains, #66)
        for _col in ("requested_model", "actual_model"):
            try:
                await self._db.execute(
                    f"ALTER TABLE execution_records ADD COLUMN {_col} TEXT"
                )
                await self._db.commit()
            except Exception as exc:
                logger.debug("Migration already applied or failed: %s", exc)
        # Migration: generalized cost columns (issue #79)
        for _col, _decl in (
            ("unit", "TEXT DEFAULT 'tokens'"), ("quantity", "REAL"),
            ("unit_price", "REAL"), ("provenance", "TEXT DEFAULT 'litellm'"),
        ):
            try:
                await self._db.execute(
                    f"ALTER TABLE cost_records ADD COLUMN {_col} {_decl}"
                )
                await self._db.commit()
            except Exception as exc:
                logger.debug("Migration already applied or failed: %s", exc)
        # Migration: add session_name column to existing cao_sessions table
        try:
            await self._db.execute(
                "ALTER TABLE cao_sessions ADD COLUMN session_name TEXT"
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Migration already applied or failed: %s", exc)
        await self._db.commit()

        # Auto-orphan any active CAO sessions from previous crashed runs
        try:
            cursor = await self._db.execute(
                "SELECT terminal_id FROM cao_sessions WHERE status = 'active'"
            )
            rows = await cursor.fetchall()
            stale_ids = [r[0] for r in rows]
            if stale_ids:
                await self.mark_cao_sessions_orphaned(stale_ids)
                logger.info(
                    "Marked %d stale CAO sessions as orphaned on startup",
                    len(stale_ids),
                )
        except Exception as exc:
            logger.debug("CAO session orphan check failed: %s", exc)

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
               skipped_nodes, forked_from, forked_at_step, total_cost,
               workflow_path, workflow_hash, resumed_from, git_sha, git_dirty,
               observed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_summary.run_id,
                run_summary.workflow_name,
                run_summary.status,
                run_summary.started_at.isoformat(),
                run_summary.completed_at.isoformat() if run_summary.completed_at else None,
                run_summary.total_nodes,
                run_summary.completed_nodes,
                run_summary.failed_nodes,
                run_summary.skipped_nodes,
                run_summary.forked_from,
                run_summary.forked_at_step,
                run_summary.total_cost,
                run_summary.workflow_path,
                run_summary.workflow_hash,
                run_summary.resumed_from,
                run_summary.git_sha,
                int(run_summary.git_dirty),
                int(run_summary.observed),
            ),
        )
        await db.commit()

    async def get_run(self, run_id: str) -> RunSummary | None:
        db = await self._ensure_initialized()
        cursor = await db.execute(
            self._RUNS_SELECT + " WHERE run_id = ?",
            (run_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run_summary(row)

    async def update_run(self, run_summary: RunSummary) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            """UPDATE runs SET workflow_name=?, status=?, started_at=?,
               completed_at=?, total_nodes=?, completed_nodes=?, failed_nodes=?,
               skipped_nodes=?, forked_from=?, forked_at_step=?, total_cost=?,
               workflow_path=?, workflow_hash=?, resumed_from=?,
               git_sha=?, git_dirty=?, observed=?
               WHERE run_id=?""",
            (
                run_summary.workflow_name,
                run_summary.status,
                run_summary.started_at.isoformat(),
                run_summary.completed_at.isoformat() if run_summary.completed_at else None,
                run_summary.total_nodes,
                run_summary.completed_nodes,
                run_summary.failed_nodes,
                run_summary.skipped_nodes,
                run_summary.forked_from,
                run_summary.forked_at_step,
                run_summary.total_cost,
                run_summary.workflow_path,
                run_summary.workflow_hash,
                run_summary.resumed_from,
                run_summary.git_sha,
                int(run_summary.git_dirty),
                int(run_summary.observed),
                run_summary.run_id,
            ),
        )
        await db.commit()

    _RUNS_SELECT = (
        "SELECT run_id, workflow_name, status, started_at, completed_at,"
        " total_nodes, completed_nodes, failed_nodes, skipped_nodes,"
        " forked_from, forked_at_step, total_cost, workflow_path,"
        " workflow_hash, resumed_from, git_sha, git_dirty, observed FROM runs"
    )

    async def list_runs(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[RunSummary]:
        db = await self._ensure_initialized()
        query = self._RUNS_SELECT
        params: list[int] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            # SQLite requires LIMIT when OFFSET is used; use -1 for unlimited.
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_run_summary(row) for row in rows]

    async def record(self, execution_record: ExecutionRecord) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            """INSERT INTO execution_records (id, run_id, task_id, parent_task_id,
               agent_id, status, input_artifact_refs, output_artifact_refs,
               prompt, model, tool_calls, latency_ms, timestamp, trace_id, error,
               trace_events, requested_model, actual_model)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                json.dumps(execution_record.trace_events)
                if execution_record.trace_events
                else None,
                execution_record.requested_model,
                execution_record.actual_model,
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
    def _row_to_run_summary(row: aiosqlite.Row | tuple) -> RunSummary:  # type: ignore[type-arg]
        return RunSummary(
            run_id=row[0],
            workflow_name=row[1],
            status=row[2],
            started_at=datetime.fromisoformat(row[3]),
            completed_at=datetime.fromisoformat(row[4]) if row[4] else None,
            total_nodes=row[5],
            completed_nodes=row[6],
            failed_nodes=row[7],
            skipped_nodes=row[8] if row[8] is not None else 0,
            forked_from=row[9] if len(row) > 9 else None,
            forked_at_step=row[10] if len(row) > 10 else None,
            total_cost=float(row[11]) if row[11] is not None else 0.0,
            workflow_path=row[12] if row[12] is not None else None,
            workflow_hash=str(row[13]) if row[13] is not None else None,
            resumed_from=row[14] if len(row) > 14 and row[14] is not None else None,
            git_sha=row[15] if len(row) > 15 and row[15] is not None else None,
            git_dirty=bool(row[16]) if len(row) > 16 and row[16] is not None else False,
            observed=bool(row[17]) if len(row) > 17 and row[17] is not None else False,
        )

    async def record_cost(self, cost_record: CostRecord) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            """INSERT INTO cost_records (id, run_id, task_id, cost, currency,
               source, prompt_tokens, completion_tokens, model, timestamp,
               unit, quantity, unit_price, provenance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                cost_record.unit,
                cost_record.quantity,
                cost_record.unit_price,
                cost_record.provenance,
            ),
        )
        await db.commit()
        # Update in-memory running totals. Replay (#74) is experimentation spend
        # and is excluded from run-level aggregation.
        if cost_record.source != "replay":
            run_totals = self._node_costs.setdefault(cost_record.run_id, {})
            run_totals[cost_record.task_id] = (
                run_totals.get(cost_record.task_id, 0.0) + cost_record.cost
            )

    async def list_costs(self, run_id: str) -> list[CostRecord]:
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT * FROM cost_records WHERE run_id = ? ORDER BY timestamp",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_cost_record(row) for row in rows]

    async def list_costs_batch(self, run_ids: list[str]) -> list[CostRecord]:
        """Fetch cost records for multiple run_ids in a single query."""
        if not run_ids:
            return []
        db = await self._ensure_initialized()
        ph = ",".join("?" for _ in run_ids)
        cursor = await db.execute(
            "SELECT * FROM cost_records WHERE run_id IN (" + ph + ") ORDER BY timestamp",
            run_ids,
        )
        rows = await cursor.fetchall()
        return [self._row_to_cost_record(row) for row in rows]

    async def get_cost_aggregations(
        self, run_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Return SQL-aggregated cost breakdowns by model, node, and date."""
        if not run_ids:
            return {"by_model": [], "by_node": [], "by_date": []}
        db = await self._ensure_initialized()
        ph = ",".join("?" for _ in run_ids)
        in_clause = "(" + ph + ")"

        # By model
        cursor = await db.execute(
            "SELECT COALESCE(model, 'unknown') as m, SUM(cost) as total, COUNT(*) as cnt "
            "FROM cost_records WHERE run_id IN " + in_clause + " "
            "GROUP BY m ORDER BY total DESC",
            run_ids,
        )
        by_model = [
            {"model": row[0], "cost": round(row[1], 6), "count": row[2]}
            for row in await cursor.fetchall()
        ]

        # By node (task_id)
        cursor = await db.execute(
            "SELECT task_id, SUM(cost) as total, COUNT(*) as cnt "
            "FROM cost_records WHERE run_id IN " + in_clause + " "
            "GROUP BY task_id ORDER BY total DESC",
            run_ids,
        )
        by_node = [
            {"node_id": row[0], "cost": round(row[1], 6), "count": row[2]}
            for row in await cursor.fetchall()
        ]

        # By date
        cursor = await db.execute(
            "SELECT DATE(timestamp) as d, SUM(cost) as total, COUNT(DISTINCT run_id) as runs "
            "FROM cost_records WHERE run_id IN " + in_clause + " "
            "GROUP BY d ORDER BY d",
            run_ids,
        )
        by_date = [
            {"date": row[0], "cost": round(row[1], 6), "runs": row[2]}
            for row in await cursor.fetchall()
        ]

        return {"by_model": by_model, "by_node": by_node, "by_date": by_date}

    async def get_node_cost(self, run_id: str, task_id: str) -> float:
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM cost_records WHERE run_id = ? AND task_id = ?",
            (run_id, task_id),
        )
        row = await cursor.fetchone()
        return float(row[0]) if row is not None else 0.0

    async def get_run_cost_summary(self, run_id: str) -> RunCostSummary:
        # Serve from in-memory totals if available (populated by record_cost)
        if run_id in self._node_costs:
            node_costs = dict(self._node_costs[run_id])
            return RunCostSummary(
                run_id=run_id,
                total_cost=sum(node_costs.values()),
                node_costs=node_costs,
            )
        # Fallback to SQL for runs recorded by other store instances or before restart
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT task_id, SUM(cost) FROM cost_records "
            "WHERE run_id = ? AND source != 'replay' GROUP BY task_id",
            (run_id,),
        )
        rows = await cursor.fetchall()
        node_costs = {row[0]: float(row[1]) for row in rows}
        total_cost = sum(node_costs.values())
        return RunCostSummary(
            run_id=run_id,
            total_cost=total_cost,
            node_costs=node_costs,
        )

    @staticmethod
    def _row_to_cost_record(row: aiosqlite.Row | tuple) -> CostRecord:  # type: ignore[type-arg]
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
            unit=row[10] if len(row) > 10 and row[10] is not None else "tokens",
            quantity=row[11] if len(row) > 11 else None,
            unit_price=row[12] if len(row) > 12 else None,
            provenance=row[13] if len(row) > 13 and row[13] is not None else "litellm",
        )

    @staticmethod
    def _row_to_execution_record(row: aiosqlite.Row | tuple) -> ExecutionRecord:  # type: ignore[type-arg]
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
            trace_events=json.loads(row[15]) if len(row) > 15 and row[15] else None,
            requested_model=row[16] if len(row) > 16 else None,
            actual_model=row[17] if len(row) > 17 else None,
        )

    # ------------------------------------------------------------------
    # CAO session registry
    # ------------------------------------------------------------------

    async def create_cao_session(
        self, terminal_id: str, run_id: str, node_name: str,
        session_name: str | None = None,
    ) -> None:
        """Persist an active CAO session."""
        db = await self._ensure_initialized()
        await db.execute(
            "INSERT INTO cao_sessions "
            "(terminal_id, run_id, node_name, started_at, status, session_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (terminal_id, run_id, node_name,
             datetime.now(UTC).isoformat(), "active", session_name),
        )
        await db.commit()

    async def complete_cao_session(self, terminal_id: str) -> None:
        """Mark session as completed (soft delete)."""
        db = await self._ensure_initialized()
        await db.execute(
            "UPDATE cao_sessions SET status = 'completed', completed_at = datetime('now') "
            "WHERE terminal_id = ?",
            (terminal_id,),
        )
        await db.commit()

    async def get_cao_sessions(
        self, status: str | None = None,
    ) -> list[dict[str, str]]:
        """List CAO sessions, optionally filtered by status."""
        db = await self._ensure_initialized()
        if status:
            cursor = await db.execute(
                "SELECT terminal_id, run_id, node_name, started_at, status, session_name "
                "FROM cao_sessions WHERE status = ?",
                (status,),
            )
        else:
            cursor = await db.execute(
                "SELECT terminal_id, run_id, node_name, started_at, status, session_name "
                "FROM cao_sessions",
            )
        rows = await cursor.fetchall()
        return [
            {
                "terminal_id": r[0],
                "run_id": r[1],
                "node_name": r[2],
                "started_at": r[3],
                "status": r[4],
                "session_name": r[5],
            }
            for r in rows
        ]

    async def get_orphaned_cao_sessions(self) -> list[dict[str, str]]:
        """Return sessions with status 'orphaned'."""
        return await self.get_cao_sessions(status="orphaned")

    async def mark_cao_sessions_orphaned(self, terminal_ids: list[str]) -> None:
        """Mark active sessions as orphaned (crash recovery)."""
        if not terminal_ids:
            return
        db = await self._ensure_initialized()
        ph = ",".join("?" for _ in terminal_ids)
        await db.execute(
            "UPDATE cao_sessions SET status = 'orphaned' WHERE terminal_id IN (" + ph + ")",
            terminal_ids,
        )
        await db.commit()

    async def delete_cao_session(self, terminal_id: str) -> bool:
        """Delete a session by terminal_id. Returns True if deleted."""
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "DELETE FROM cao_sessions WHERE terminal_id = ?", (terminal_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def store_workflow_snapshot(self, content: str, version: int) -> str:
        """Store workflow YAML content, deduplicated by SHA256 hash. Returns hash."""
        db = await self._ensure_initialized()
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        await db.execute(
            """INSERT OR IGNORE INTO workflow_snapshots (hash, content, version, created_at)
               VALUES (?, ?, ?, ?)""",
            (content_hash, content, version, datetime.now(UTC).isoformat()),
        )
        await db.commit()
        return content_hash

    async def get_workflow_snapshot(self, content_hash: str) -> dict[str, Any] | None:
        """Retrieve a workflow snapshot by hash."""
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT hash, content, version, created_at FROM workflow_snapshots WHERE hash = ?",
            (content_hash,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return {"hash": row[0], "content": row[1], "version": row[2], "created_at": row[3]}

    # ------------------------------------------------------------------
    # Node cache
    # ------------------------------------------------------------------

    async def get_cache_entry(self, cache_key: str) -> CacheEntry | None:
        db = await self._ensure_initialized()
        cursor = await db.execute(
            "SELECT cache_key, run_id, node_id, artifact_ids, saved_cost, created_at"
            " FROM cache_entries WHERE cache_key = ?",
            (cache_key,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return CacheEntry(
            cache_key=row[0], run_id=row[1], node_id=row[2],
            artifact_ids=json.loads(row[3]), saved_cost=float(row[4] or 0.0),
            created_at=datetime.fromisoformat(row[5]),
        )

    async def put_cache_entry(self, entry: CacheEntry) -> None:
        db = await self._ensure_initialized()
        await db.execute(
            "INSERT OR REPLACE INTO cache_entries"
            " (cache_key, run_id, node_id, artifact_ids, saved_cost, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                entry.cache_key, entry.run_id, entry.node_id,
                json.dumps(entry.artifact_ids), entry.saved_cost,
                entry.created_at.isoformat(),
            ),
        )
        await db.commit()

    async def count_cache_entries(self) -> int:
        db = await self._ensure_initialized()
        cursor = await db.execute("SELECT COUNT(*) FROM cache_entries")
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def clear_cache_entries(self, older_than_days: float | None = None) -> int:
        db = await self._ensure_initialized()
        if older_than_days is None:
            cursor = await db.execute("DELETE FROM cache_entries")
        else:
            from datetime import timedelta

            cutoff = (datetime.now(UTC) - timedelta(days=older_than_days)).isoformat()
            cursor = await db.execute(
                "DELETE FROM cache_entries WHERE created_at < ?", (cutoff,),
            )
        await db.commit()
        return cursor.rowcount if cursor.rowcount is not None else 0


__all__ = ["SqliteExecutionStore"]
