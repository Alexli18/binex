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
        self._loop_contains: dict[str, list[str]] = {}
        self._loop_subgraphs: dict[str, DAG] = {}

    @classmethod
    def from_workflow(cls, spec: WorkflowSpec) -> DAG:
        # Identify loop containers and their contained nodes
        loop_contains: dict[str, list[str]] = {}
        contained_nodes: set[str] = set()
        for node_id, node in spec.nodes.items():
            if node.type == "loop" and node.loop:
                loop_contains[node_id] = node.loop.contains
                contained_nodes.update(node.loop.contains)

        # Top-level nodes = all nodes minus contained nodes
        top_level_ids = set(spec.nodes.keys()) - contained_nodes
        forward: dict[str, set[str]] = {nid: set() for nid in top_level_ids}
        backward: dict[str, set[str]] = {nid: set() for nid in top_level_ids}

        for node_id in top_level_ids:
            node = spec.nodes[node_id]
            if node.type == "loop" and node.loop:
                # Loop container inherits dependencies of its entry nodes
                # (contained nodes whose deps are outside the loop)
                contains_set = set(node.loop.contains)
                for child_id in node.loop.contains:
                    if child_id not in spec.nodes:
                        continue
                    child = spec.nodes[child_id]
                    for dep in child.depends_on:
                        if dep not in contains_set and dep in top_level_ids:
                            backward[node_id].add(dep)
                            forward[dep].add(node_id)
                # Also add explicit depends_on of the loop container itself
                for dep in node.depends_on:
                    if dep in top_level_ids:
                        backward[node_id].add(dep)
                        forward[dep].add(node_id)
            else:
                for dep in node.depends_on:
                    if dep in contained_nodes:
                        # This node depends on a contained node → depends on its loop container
                        for loop_id, children in loop_contains.items():
                            if dep in children:
                                backward[node_id].add(loop_id)
                                forward[loop_id].add(node_id)
                                break
                    elif dep in top_level_ids:
                        forward[dep].add(node_id)
                        backward[node_id].add(dep)
                    else:
                        raise ValueError(
                            f"Node '{node_id}' depends on unknown node '{dep}'"
                        )

        dag = cls(nodes=top_level_ids, forward=forward, backward=backward)
        dag._loop_contains = loop_contains
        dag.topological_order()  # validates acyclicity

        # Build sub-graphs for each loop
        for loop_id, children in loop_contains.items():
            dag._loop_subgraphs[loop_id] = cls._build_loop_subgraph(
                spec, loop_id, children,
            )

        return dag

    @classmethod
    def _build_loop_subgraph(
        cls, spec: WorkflowSpec, loop_id: str, contains: list[str],
    ) -> DAG:
        """Build internal DAG for a loop's contained nodes."""
        child_ids = set(contains)
        forward: dict[str, set[str]] = {nid: set() for nid in child_ids}
        backward: dict[str, set[str]] = {nid: set() for nid in child_ids}

        for nid in child_ids:
            if nid not in spec.nodes:
                continue
            for dep in spec.nodes[nid].depends_on:
                if dep in child_ids:
                    forward[dep].add(nid)
                    backward[nid].add(dep)

        sub = cls(nodes=child_ids, forward=forward, backward=backward)
        sub.topological_order()
        return sub

    def get_loop_subgraph(self, loop_node_id: str) -> DAG:
        """Return the internal DAG for a loop container."""
        if loop_node_id not in self._loop_subgraphs:
            raise KeyError(f"No loop subgraph for '{loop_node_id}'")
        return self._loop_subgraphs[loop_node_id]

    def get_loop_contains(self, loop_node_id: str) -> list[str]:
        """Return contained node IDs for a loop container."""
        return self._loop_contains.get(loop_node_id, [])

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
