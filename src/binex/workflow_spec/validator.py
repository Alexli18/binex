"""Workflow structural validator — checks DAG integrity and interpolation targets."""

from __future__ import annotations

import re
from collections import deque

from binex.models.workflow import WorkflowSpec

_INTERPOLATION_RE = re.compile(r"\$\{(\w+)\.(\w+)\}")


_WHEN_RE = re.compile(r"^\$\{(\w+)\.(\w+)\}\s*(==|!=)\s*(.+)$")


def validate_workflow(spec: WorkflowSpec) -> list[str]:
    """Validate workflow structure. Returns a list of error messages (empty = valid)."""
    errors: list[str] = []
    node_ids = set(spec.nodes.keys())

    _check_depends_on_refs(spec, node_ids, errors)
    _check_interpolation_targets(spec, node_ids, errors)
    _check_cycles(spec, node_ids, errors)
    _check_entry_nodes(spec, node_ids, errors)
    _check_when_conditions(spec, node_ids, errors)
    _check_output_schemas(spec, node_ids, errors)

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


def _validate_interpolations_in_string(
    value: str,
    node_id: str,
    key: str,
    spec: WorkflowSpec,
    node_ids: set[str],
    errors: list[str],
) -> None:
    """Validate all interpolation references within a single string value."""
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


def _check_value_interpolations(
    value: object,
    node_id: str,
    key: str,
    spec: WorkflowSpec,
    node_ids: set[str],
    errors: list[str],
) -> None:
    if isinstance(value, str):
        _validate_interpolations_in_string(value, node_id, key, spec, node_ids, errors)
    elif isinstance(value, list):
        for item in value:
            _check_value_interpolations(item, node_id, key, spec, node_ids, errors)
    elif isinstance(value, dict):
        for v in value.values():
            _check_value_interpolations(v, node_id, key, spec, node_ids, errors)


def _build_in_degree_and_adj(
    spec: WorkflowSpec, node_ids: set[str],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Build in-degree map and adjacency list from workflow spec."""
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for node in spec.nodes.values():
        for dep in node.depends_on:
            if dep in node_ids:
                in_degree[node.id] += 1
                adj[dep].append(node.id)
    return in_degree, adj


def _run_kahn_algorithm(
    in_degree: dict[str, int], adj: dict[str, list[str]],
) -> int:
    """Run Kahn's topological sort. Returns the number of visited nodes."""
    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for neighbor in adj[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    return visited


def _check_cycles(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    """Detect cycles using Kahn's algorithm."""
    in_degree, adj = _build_in_degree_and_adj(spec, node_ids)
    visited = _run_kahn_algorithm(in_degree, adj)

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


def _check_when_conditions(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    """Validate when-condition syntax and references."""
    for node_id, node in spec.nodes.items():
        if node.when is None:
            continue
        m = _WHEN_RE.match(node.when.strip())
        if not m:
            errors.append(
                f"Node '{node_id}': when condition has invalid syntax: {node.when!r}"
            )
            continue
        ref_node = m.group(1)
        if ref_node not in node_ids:
            errors.append(
                f"Node '{node_id}': when condition references unknown node '{ref_node}'"
            )
        elif ref_node not in node.depends_on:
            errors.append(
                f"Node '{node_id}': when condition references node '{ref_node}' "
                f"which is not in depends_on"
            )


def _check_output_schemas(
    spec: WorkflowSpec, node_ids: set[str], errors: list[str],
) -> None:
    """Validate that output_schema fields are valid JSON Schemas."""
    for node_id, node in spec.nodes.items():
        if node.output_schema is None:
            continue
        if not isinstance(node.output_schema, dict):
            errors.append(
                f"Node '{node_id}': output_schema must be a JSON Schema object (dict)"
            )
            continue
        try:
            import jsonschema
            validator_cls = jsonschema.validators.validator_for(node.output_schema)
            validator_cls.check_schema(node.output_schema)
        except jsonschema.exceptions.SchemaError as e:
            errors.append(
                f"Node '{node_id}': invalid JSON Schema in output_schema: {e.message}"
            )
