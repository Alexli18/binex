"""Workflow structural validator — checks DAG integrity and interpolation targets."""

from __future__ import annotations

import logging
import os
import re
from collections import deque

from binex.models.workflow import CaoConfig, WorkflowSpec

logger = logging.getLogger(__name__)

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
    _check_schedule_cron(spec, errors)
    _check_tool_uris(spec, errors)
    _check_cao_nodes(spec, errors)

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


def _check_schedule_cron(
    spec: WorkflowSpec, errors: list[str],
) -> None:
    """Validate cron expression in schedule field, if present."""
    if spec.schedule is None:
        return
    try:
        from croniter import croniter
        if not croniter.is_valid(spec.schedule):
            errors.append(
                f"Invalid cron expression in schedule: {spec.schedule!r}"
            )
    except ImportError:
        errors.append(
            "croniter package is required for schedule validation — "
            "install it with: pip install croniter"
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


def _validate_builtin_tool_uri(
    node_id: str, tool_spec: str, available_builtins: set[str], errors: list[str],
) -> None:
    """Validate a single builtin:// tool URI."""
    name = tool_spec[len("builtin://"):]
    if name not in available_builtins:
        errors.append(
            f"Node '{node_id}': unknown built-in tool '{name}'. "
            f"Available: {', '.join(sorted(available_builtins))}"
        )


def _validate_mcp_tool_uri(
    node_id: str, tool_spec: str, mcp_server_names: set[str], errors: list[str],
) -> None:
    """Validate a single mcp:// tool URI."""
    server = tool_spec[len("mcp://"):]
    if server not in mcp_server_names:
        errors.append(
            f"Node '{node_id}': mcp:// references "
            f"unknown server '{server}'. "
            f"Declared mcp_servers: "
            f"{', '.join(sorted(mcp_server_names)) or '(none)'}"
        )


def _check_tool_uris(
    spec: WorkflowSpec, errors: list[str],
) -> None:
    """Validate builtin:// and mcp:// tool URIs in node tools lists."""
    from binex.tools.builtins import list_builtins

    available_builtins = set(list_builtins())
    mcp_server_names = set(spec.mcp_servers.keys())

    for node_id, node in spec.nodes.items():
        for tool_spec in node.tools:
            if not isinstance(tool_spec, str):
                continue
            if tool_spec.startswith("builtin://"):
                _validate_builtin_tool_uri(node_id, tool_spec, available_builtins, errors)
            elif tool_spec.startswith("mcp://"):
                _validate_mcp_tool_uri(node_id, tool_spec, mcp_server_names, errors)


def _validate_cao_config(node_id: str, cao: CaoConfig, errors: list[str]) -> None:
    """Validate a single node's CaoConfig fields."""
    if cao.output_field and cao.output_format != "json":
        errors.append(
            f"Node '{node_id}': cao output_field requires "
            f"output_format='json', got '{cao.output_format}'"
        )
    if cao.output_field and not cao.output_field.startswith("$."):
        errors.append(
            f"Node '{node_id}': cao output_field must be a JSONPath "
            f"starting with '$.' — got '{cao.output_field}'"
        )
    if cao.timeout_minutes < 1:
        errors.append(
            f"Node '{node_id}': cao timeout_minutes must be >= 1, "
            f"got {cao.timeout_minutes}"
        )


def _check_cao_nodes(
    spec: WorkflowSpec, errors: list[str],
) -> None:
    """Validate CAO-specific fields on cao:// nodes."""
    for node_id, node in spec.nodes.items():
        if not node.agent.startswith("cao://"):
            continue
        if node.cao is not None:
            _validate_cao_config(node_id, node.cao, errors)


def validate_cao_warnings(
    spec: WorkflowSpec,
    agent_store_dir: str | None = None,
    cao_server_url: str | None = None,
) -> list[str]:
    """Soft-validate CAO nodes — returns warnings (not errors).

    Checks:
    1. CAO server reachable (grey info if not)
    2. Profile .md file exists in agent-store (yellow warning if not)
    """
    warnings: list[str] = []
    cao_nodes = {
        nid: node for nid, node in spec.nodes.items()
        if node.agent.startswith("cao://")
    }
    if not cao_nodes:
        return warnings

    store_dir = agent_store_dir or os.path.expanduser(
        "~/.aws/cli-agent-orchestrator/agent-store"
    )
    server_url = (cao_server_url or "http://localhost:9889").rstrip("/")

    # Check CAO server health (best-effort, sync-safe)
    server_reachable = _cao_server_reachable(server_url)
    if not server_reachable:
        warnings.append(
            f"Cannot validate CAO profiles: server not running at {server_url}"
        )

    # Check profiles exist on disk
    for node_id, node in cao_nodes.items():
        profile = node.agent.removeprefix("cao://")
        profile_path = os.path.join(store_dir, f"{profile}.md")
        if not os.path.isfile(profile_path):
            warnings.append(
                f"Node '{node_id}': CAO profile '{profile}' not found at "
                f"{profile_path}. Install with: cao profile install {profile}"
            )

    return warnings


def _cao_server_reachable(server_url: str) -> bool:
    """Check if CAO server is reachable (sync, best-effort).

    Note: uses synchronous httpx.get() — acceptable here because
    validate_cao_warnings() is called from sync CLI context, not from
    an async event loop. In async contexts, call from a thread pool.
    """
    try:
        import httpx

        resp = httpx.get(f"{server_url}/health", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False
