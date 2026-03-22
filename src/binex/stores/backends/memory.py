"""In-memory store backends for testing."""

from __future__ import annotations

import hashlib
from collections import deque
from typing import Any

from binex.models.artifact import Artifact
from binex.models.cost import CostRecord, RunCostSummary
from binex.models.execution import ExecutionRecord, RunSummary


class InMemoryArtifactStore:
    """In-memory artifact store for tests."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    async def store(self, artifact: Artifact) -> None:
        self._artifacts[artifact.id] = artifact

    async def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    async def list_by_run(self, run_id: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.run_id == run_id]

    async def get_lineage(self, artifact_id: str) -> list[Artifact]:
        result: list[Artifact] = []
        visited: set[str] = set()
        queue = deque([artifact_id])
        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)
            art = self._artifacts.get(current_id)
            if art is None:
                continue
            if current_id != artifact_id:
                result.append(art)
            queue.extend(art.lineage.derived_from)
        return result


class InMemoryExecutionStore:
    """In-memory execution store for tests."""

    def __init__(self) -> None:
        self._runs: dict[str, RunSummary] = {}
        self._records: list[ExecutionRecord] = []
        self._cost_records: list[CostRecord] = []
        self._cao_sessions: dict[str, dict[str, str]] = {}
        self._workflow_snapshots: dict[str, dict[str, Any]] = {}

    async def close(self) -> None:
        pass

    async def record(self, execution_record: ExecutionRecord) -> None:
        self._records.append(execution_record)

    async def get_run(self, run_id: str) -> RunSummary | None:
        return self._runs.get(run_id)

    async def get_step(self, run_id: str, task_id: str) -> ExecutionRecord | None:
        for rec in self._records:
            if rec.run_id == run_id and rec.task_id == task_id:
                return rec
        return None

    async def list_runs(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[RunSummary]:
        runs = list(self._runs.values())
        if limit is not None:
            return runs[offset : offset + limit]
        return runs[offset:]

    async def create_run(self, run_summary: RunSummary) -> None:
        self._runs[run_summary.run_id] = run_summary

    async def update_run(self, run_summary: RunSummary) -> None:
        self._runs[run_summary.run_id] = run_summary

    async def list_records(self, run_id: str) -> list[ExecutionRecord]:
        return [r for r in self._records if r.run_id == run_id]

    async def record_cost(self, cost_record: CostRecord) -> None:
        self._cost_records.append(cost_record)

    async def list_costs(self, run_id: str) -> list[CostRecord]:
        return [r for r in self._cost_records if r.run_id == run_id]

    async def list_costs_batch(self, run_ids: list[str]) -> list[CostRecord]:
        """Fetch cost records for multiple run_ids."""
        id_set = set(run_ids)
        return [r for r in self._cost_records if r.run_id in id_set]

    async def get_cost_aggregations(
        self, run_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Return aggregated cost breakdowns by model, node, and date."""
        records = await self.list_costs_batch(run_ids)
        if not records:
            return {"by_model": [], "by_node": [], "by_date": []}

        from collections import defaultdict

        model_agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        node_agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"cost": 0.0, "count": 0})
        date_agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"cost": 0.0, "runs": set()})
        for r in records:
            key = r.model or "unknown"
            model_agg[key]["cost"] += r.cost
            model_agg[key]["count"] += 1
            node_agg[r.task_id]["cost"] += r.cost
            node_agg[r.task_id]["count"] += 1
            date_key = r.timestamp.strftime("%Y-%m-%d")
            date_agg[date_key]["cost"] += r.cost
            date_agg[date_key]["runs"].add(r.run_id)

        by_model = [
            {"model": m, "cost": round(d["cost"], 6), "count": d["count"]}
            for m, d in sorted(model_agg.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]
        by_node = [
            {"node_id": n, "cost": round(d["cost"], 6), "count": d["count"]}
            for n, d in sorted(node_agg.items(), key=lambda x: x[1]["cost"], reverse=True)
        ]
        by_date = [
            {"date": dt, "cost": round(d["cost"], 6), "runs": len(d["runs"])}
            for dt, d in sorted(date_agg.items())
        ]
        return {"by_model": by_model, "by_node": by_node, "by_date": by_date}

    async def get_node_cost(self, run_id: str, task_id: str) -> float:
        return sum(
            r.cost for r in self._cost_records
            if r.run_id == run_id and r.task_id == task_id
        )

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

    # ------------------------------------------------------------------
    # CAO session registry
    # ------------------------------------------------------------------

    async def create_cao_session(
        self, terminal_id: str, run_id: str, node_name: str,
        session_name: str | None = None,
    ) -> None:
        self._cao_sessions[terminal_id] = {
            "terminal_id": terminal_id,
            "run_id": run_id,
            "node_name": node_name,
            "started_at": "",
            "status": "active",
            "session_name": session_name or "",
        }

    async def complete_cao_session(self, terminal_id: str) -> None:
        if terminal_id in self._cao_sessions:
            self._cao_sessions[terminal_id]["status"] = "completed"

    async def get_cao_sessions(
        self, status: str | None = None,
    ) -> list[dict[str, str]]:
        sessions = list(self._cao_sessions.values())
        if status:
            sessions = [s for s in sessions if s["status"] == status]
        return sessions

    async def get_orphaned_cao_sessions(self) -> list[dict[str, str]]:
        return await self.get_cao_sessions(status="orphaned")

    async def mark_cao_sessions_orphaned(self, terminal_ids: list[str]) -> None:
        for tid in terminal_ids:
            if tid in self._cao_sessions:
                self._cao_sessions[tid]["status"] = "orphaned"

    async def delete_cao_session(self, terminal_id: str) -> bool:
        return self._cao_sessions.pop(terminal_id, None) is not None

    # ------------------------------------------------------------------
    # Workflow snapshots
    # ------------------------------------------------------------------

    async def store_workflow_snapshot(self, content: str, version: int) -> str:
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        if content_hash not in self._workflow_snapshots:
            self._workflow_snapshots[content_hash] = {
                "hash": content_hash,
                "content": content,
                "version": version,
                "created_at": "",
            }
        return content_hash

    async def get_workflow_snapshot(self, content_hash: str) -> dict[str, Any] | None:
        return self._workflow_snapshots.get(content_hash)


__all__ = [
    "InMemoryArtifactStore",
    "InMemoryExecutionStore",
]
