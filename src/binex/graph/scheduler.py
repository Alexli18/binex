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
        self._execution_count: dict[str, int] = {}

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

    def get_execution_count(self, node_id: str) -> int:
        """Return how many times a node has been re-executed (0 = never reset)."""
        return self._execution_count.get(node_id, 0)

    def mark_pending_again(self, node_id: str) -> None:
        """Reset a completed/failed node back to pending for re-execution."""
        self._completed.discard(node_id)
        self._failed.discard(node_id)
        self._running.discard(node_id)
        self._execution_count[node_id] = self._execution_count.get(node_id, 0) + 1

    def reset_chain(self, from_node: str, to_node: str, dag: DAG) -> list[str]:
        """Reset all nodes on any path from from_node to to_node (inclusive)."""
        # Forward reachable from from_node (bounded by to_node)
        forward_reachable: set[str] = set()
        queue = [from_node]
        while queue:
            current = queue.pop(0)
            if current in forward_reachable:
                continue
            forward_reachable.add(current)
            if current == to_node:
                continue  # don't go past to_node
            for dep in sorted(dag.dependents(current)):
                queue.append(dep)

        # Backward reachable from to_node (bounded by from_node)
        backward_reachable: set[str] = set()
        queue = [to_node]
        while queue:
            current = queue.pop(0)
            if current in backward_reachable:
                continue
            backward_reachable.add(current)
            if current == from_node:
                continue
            for dep in sorted(dag.dependencies(current)):
                queue.append(dep)

        # Intersection = nodes on path from from_node to to_node
        on_path = forward_reachable & backward_reachable
        result = []
        for node_id in on_path:
            self.mark_pending_again(node_id)
            result.append(node_id)
        return sorted(result)

    def is_complete(self) -> bool:
        return self._dag.nodes <= (self._completed | self._failed | self._skipped)

    def is_blocked(self) -> bool:
        """True if no more progress can be made (failed nodes block remaining)."""
        return not self.is_complete() and not self.ready_nodes() and not self._running
