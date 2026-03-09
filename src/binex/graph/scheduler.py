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
        self._skipped: set[str] = set()

    def ready_nodes(self) -> list[str]:
        """Return node IDs whose dependencies are all completed/skipped
        and not already running/done."""
        ready = []
        satisfied = self._completed | self._skipped
        already_handled = (
            self._completed | self._failed | self._running | self._skipped
        )
        for node_id in sorted(self._dag.nodes):
            if node_id in already_handled:
                continue
            deps = self._dag.dependencies(node_id)
            if deps <= satisfied:
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

    def mark_skipped(self, node_id: str) -> None:
        self._skipped.add(node_id)

    def is_complete(self) -> bool:
        return self._dag.nodes <= (self._completed | self._failed | self._skipped)

    def is_blocked(self) -> bool:
        """True if no more progress can be made (failed nodes block remaining)."""
        return not self.is_complete() and not self.ready_nodes() and not self._running
