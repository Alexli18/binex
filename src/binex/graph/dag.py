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

    def add_node(self, node_id: str, depends_on: set[str]) -> None:
        """Insert a node (with its dependency edges) at runtime — dynamic fan-out (#77).

        The scheduler stays static in shape; this simply makes "more nodes appear".
        Callers must ensure ``depends_on`` references existing nodes and that no
        cycle is introduced (fan-out adds only forward edges, so it cannot).
        """
        self._nodes.add(node_id)
        self._forward.setdefault(node_id, set())
        self._backward.setdefault(node_id, set())
        for dep in depends_on:
            self._backward[node_id].add(dep)
            self._forward.setdefault(dep, set()).add(node_id)

    def rewire_dependents(self, old_dep: str, new_dep: str) -> None:
        """Redirect every dependent of ``old_dep`` to depend on ``new_dep`` instead.

        Used when a ``foreach`` placeholder is replaced by its aggregator: nodes
        that depended on the placeholder must now wait for the aggregator.
        """
        for dependent in list(self._forward.get(old_dep, set())):
            self._backward[dependent].discard(old_dep)
            self._backward[dependent].add(new_dep)
            self._forward.setdefault(new_dep, set()).add(dependent)
        self._forward[old_dep] = set()

    def dependencies(self, node_id: str) -> set[str]:
        return self._backward.get(node_id, set())

    def dependents(self, node_id: str) -> set[str]:
        return self._forward.get(node_id, set())

    def descendants(self, node_id: str) -> set[str]:
        """Return all nodes transitively reachable via forward edges (exclusive)."""
        result: set[str] = set()
        queue = deque(self._forward.get(node_id, set()))
        while queue:
            current = queue.popleft()
            if current in result:
                continue
            result.add(current)
            queue.extend(self._forward.get(current, set()))
        return result

    def entry_nodes(self) -> list[str]:
        return sorted(nid for nid in self._nodes if not self._backward[nid])

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """Check if ancestor is reachable from descendant via backward edges."""
        visited: set[str] = set()
        queue = deque([descendant])
        while queue:
            current = queue.popleft()
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
