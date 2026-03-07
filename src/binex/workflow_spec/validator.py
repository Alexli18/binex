"""Workflow structural validator — checks DAG integrity and interpolation targets."""

from __future__ import annotations

import re
from collections import deque

from binex.models.workflow import WorkflowSpec

_INTERPOLATION_RE = re.compile(r"\$\{(\w+)\.(\w+)\}")


def validate_workflow(spec: WorkflowSpec) -> list[str]:
    """Validate workflow structure. Returns a list of error messages (empty = valid)."""
    errors: list[str] = []
    node_ids = set(spec.nodes.keys())

    _check_depends_on_refs(spec, node_ids, errors)
    _check_interpolation_targets(spec, node_ids, errors)
    _check_cycles(spec, node_ids, errors)
    _check_entry_nodes(spec, node_ids, errors)

    return errors


def _check_depends_on_refs(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    for node_id, node in spec.nodes.items():
        for dep in node.depends_on:
            if dep not in node_ids:
                errors.append(
                    f"Node '{node_id}': depends_on references unknown node '{dep}'"
                )


def _check_interpolation_targets(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    for node_id, node in spec.nodes.items():
        for key, value in node.inputs.items():
            _check_value_interpolations(value, node_id, key, spec, node_ids, errors)


def _check_value_interpolations(
    value: object,
    node_id: str,
    key: str,
    spec: WorkflowSpec,
    node_ids: set[str],
    errors: list[str],
) -> None:
    if isinstance(value, str):
        for match in _INTERPOLATION_RE.finditer(value):
            ref_node, ref_output = match.group(1), match.group(2)
            if ref_node == "user":
                continue
            if ref_node not in node_ids:
                errors.append(
                    f"Node '{node_id}', input '{key}': "
                    f"interpolation references unknown node '{ref_node}'"
                )
            elif ref_output not in spec.nodes[ref_node].outputs:
                errors.append(
                    f"Node '{node_id}', input '{key}': "
                    f"interpolation references unknown output '{ref_output}' "
                    f"on node '{ref_node}'"
                )
    elif isinstance(value, list):
        for item in value:
            _check_value_interpolations(item, node_id, key, spec, node_ids, errors)
    elif isinstance(value, dict):
        for v in value.values():
            _check_value_interpolations(v, node_id, key, spec, node_ids, errors)


def _check_cycles(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    """Detect cycles using Kahn's algorithm."""
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    for node in spec.nodes.values():
        for dep in node.depends_on:
            if dep in node_ids:
                in_degree[node.id] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    visited = 0

    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for node in spec.nodes.values():
        for dep in node.depends_on:
            if dep in node_ids:
                adj[dep].append(node.id)

    while queue:
        current = queue.popleft()
        visited += 1
        for neighbor in adj[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited < len(node_ids):
        cycle_nodes = [nid for nid, deg in in_degree.items() if deg > 0]
        errors.append(
            f"Dependency cycle detected involving nodes: {', '.join(sorted(cycle_nodes))}"
        )


def _check_entry_nodes(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    has_entry = any(len(node.depends_on) == 0 for node in spec.nodes.values())
    if not has_entry:
        errors.append("Workflow has no entry nodes (all nodes have dependencies)")
