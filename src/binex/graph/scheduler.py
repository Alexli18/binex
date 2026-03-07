"""Scheduler — tracks ready nodes based on dependency completion."""

from __future__ import annotations

from binex.graph.dag import DAG


class Scheduler:
    """Tracks node completion and yields ready nodes for execution."""

    def __init__(self, dag: DAG) -> None:
        self._dag = dag
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._running: set[str] = set()

    def ready_nodes(self) -> list[str]:
        """Return node IDs whose dependencies are all completed and not already running/done."""
        ready = []
        for node_id in sorted(self._dag.nodes):
            if node_id in self._completed or node_id in self._failed or node_id in self._running:
                continue
            deps = self._dag.dependencies(node_id)
            if deps <= self._completed:
                ready.append(node_id)
        return ready

    def mark_running(self, node_id: str) -> None:
        self._running.add(node_id)

    def mark_completed(self, node_id: str) -> None:
        self._running.discard(node_id)
        self._completed.add(node_id)

    def mark_failed(self, node_id: str) -> None:
        self._running.discard(node_id)
        self._failed.add(node_id)

    def is_complete(self) -> bool:
        return self._completed == self._dag.nodes

    def is_blocked(self) -> bool:
        """True if no more progress can be made (failed nodes block remaining)."""
        return not self.is_complete() and not self.ready_nodes() and not self._running
