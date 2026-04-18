"""PatternExpander — finds pattern nodes in a WorkflowSpec and expands them."""

from __future__ import annotations

from binex.models.workflow import BackEdge, WorkflowSpec
from binex.patterns.models import PatternSpec, StepConfig
from binex.patterns.templates import expand_pattern


def expand_patterns(spec: WorkflowSpec) -> WorkflowSpec:
    """Find pattern nodes in spec, expand them into sub-DAG nodes."""
    from binex.models.workflow import NodeSpec

    expanded_nodes: dict[str, NodeSpec] = {}
    pattern_exits: dict[str, str] = {}  # pattern_id -> exit_node_id

    # Separate pattern nodes from regular nodes
    regular_nodes: dict[str, NodeSpec] = {}
    for node_id, node in spec.nodes.items():
        if node.pattern:
            # Build steps dict from config if present
            steps_raw = (node.config or {}).get("steps", {})
            steps: dict[str, StepConfig] = {}
            for k, v in steps_raw.items():
                if isinstance(v, dict):
                    steps[k] = StepConfig(**v)
                elif isinstance(v, StepConfig):
                    steps[k] = v

            pspec = PatternSpec(
                id=node_id,
                pattern=node.pattern,
                model=node.agent,
                system_prompt=node.system_prompt or "",
                config={
                    k: v
                    for k, v in (node.config or {}).items()
                    if k != "steps"
                },
                steps=steps,
                depends_on=node.depends_on or [],
                inputs=node.inputs or {},
                outputs=node.outputs or [],
                budget=node.budget,
            )
            nodes, edges, back_edges = expand_pattern(pspec)
            for n in nodes:
                expanded_nodes[n.id] = n

            # Track exit node for dependency rewiring
            pattern_exits[node_id] = nodes[-1].id

            # Apply back_edges
            for be in back_edges:
                target_node = expanded_nodes[be["node_id"]]
                target_node.back_edge = BackEdge(
                    target=be["target"],
                    when=be.get("when", "true"),
                    max_iterations=be.get("max_iterations", 5),
                )
        else:
            regular_nodes[node_id] = node

    if not expanded_nodes:
        return spec  # No patterns, return unchanged

    # Rewire depends_on: any node depending on a pattern ID -> depend on exit node
    for node in regular_nodes.values():
        node.depends_on = [
            pattern_exits.get(dep, dep) for dep in (node.depends_on or [])
        ]
    for node in expanded_nodes.values():
        node.depends_on = [
            pattern_exits.get(dep, dep) for dep in (node.depends_on or [])
        ]

    # Merge all nodes
    all_nodes = {**regular_nodes, **expanded_nodes}

    return WorkflowSpec(
        version=spec.version,
        name=spec.name,
        description=spec.description,
        nodes=all_nodes,
        defaults=spec.defaults,
        budget=spec.budget,
        webhook=spec.webhook,
        mcp_servers=spec.mcp_servers,
        schedule=spec.schedule,
        source_path=spec.source_path,
    )
