"""DAG construction, topological sort, and cycle detection."""

from __future__ import annotations

from collections import deque

from binex.models.workflow import WorkflowSpec


class CycleError(Exception):
    """Raised when a cycle is detected in the workflow DAG."""


class DAG:
    """Directed acyclic graph built from a WorkflowSpec."""

    def __init__(
        self,
        nodes: set[str],
        forward: dict[str, set[str]],
        backward: dict[str, set[str]],
    ) -> None:
        self._nodes = nodes
        self._forward = forward  # node -> set of dependents
        self._backward = backward  # node -> set of dependencies

    @classmethod
    def from_workflow(cls, spec: WorkflowSpec) -> DAG:
        node_ids = set(spec.nodes.keys())
        forward: dict[str, set[str]] = {nid: set() for nid in node_ids}
        backward: dict[str, set[str]] = {nid: set() for nid in node_ids}

        for node_id, node in spec.nodes.items():
            for dep in node.depends_on:
                if dep not in node_ids:
                    raise ValueError(f"Node '{node_id}' depends on unknown node '{dep}'")
                forward[dep].add(node_id)
                backward[node_id].add(dep)

        dag = cls(nodes=node_ids, forward=forward, backward=backward)
        dag.topological_order()  # validates acyclicity
        return dag

    @property
    def nodes(self) -> set[str]:
        return self._nodes

    def dependencies(self, node_id: str) -> set[str]:
        return self._backward.get(node_id, set())

    def dependents(self, node_id: str) -> set[str]:
        return self._forward.get(node_id, set())

    def entry_nodes(self) -> list[str]:
        return sorted(nid for nid in self._nodes if not self._backward[nid])

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """Check if ancestor is reachable from descendant via backward edges."""
        visited: set[str] = set()
        queue = [descendant]
        while queue:
            current = queue.pop(0)
            if current == ancestor:
                return True
            if current in visited:
                continue
            visited.add(current)
            for dep in self._backward.get(current, set()):
                queue.append(dep)
        return False

    def topological_order(self) -> list[str]:
        """Kahn's algorithm for topological sort with cycle detection."""
        in_degree = {nid: len(self._backward[nid]) for nid in self._nodes}
        queue: deque[str] = deque(sorted(
            nid for nid, deg in in_degree.items() if deg == 0
        ))
        order: list[str] = []

        while queue:
            current = queue.popleft()
            order.append(current)
            for neighbor in sorted(self._forward[current]):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._nodes):
            cycle_nodes = sorted(nid for nid, deg in in_degree.items() if deg > 0)
            raise CycleError(
                f"Dependency cycle detected involving nodes: {', '.join(cycle_nodes)}"
            )
        return order
