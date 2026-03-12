"""DSL parser for workflow topology definitions (T019-T021).

Parses layer-based DSL strings like "A -> B, C -> D" into a graph
representation with nodes, edges, and dependency mappings.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedDSL:
    """Result of parsing one or more DSL strings."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    depends_on: dict[str, list[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# T021: Predefined patterns
# ---------------------------------------------------------------------------

PATTERNS: dict[str, str] = {
    "linear": "A -> B -> C",
    "fan-out": "planner -> researcher1, researcher2, researcher3",
    "fan-in": "source1, source2, source3 -> aggregator",
    "fan-out-fan-in": "planner -> r1, r2, r3 -> summarizer",
    "diamond": "A -> B, C -> D",
    "multi-stage": "A -> B, C -> D, E -> F",
    "chain-with-review": "draft -> review -> revise -> final",
    "map-reduce": "split -> worker1, worker2, worker3 -> reduce",
    "pipeline-with-validation": "input -> process -> validate -> output",
    "human-approval": "draft -> approve -> publish",
    "human-feedback": "generate -> human-review -> revise -> output",
    "conditional-routing": "classifier -> premium_handler, standard_handler -> reporter",
    "error-handling": "setup -> risky -> cleanup",
    "a2a-multi-agent": "coordinator -> researcher -> reviewer",
    "research": "planner -> researcher1, researcher2 -> validator -> summarizer",
    "secure-pipeline": "fetcher -> processor -> writer",
    "multi-provider": "planner -> researcher -> summarizer",
}


# ---------------------------------------------------------------------------
# T019-T020: Parse + validate
# ---------------------------------------------------------------------------

def parse_dsl(dsl_strings: list[str] | tuple[str, ...]) -> ParsedDSL:
    """Parse one or more DSL strings into a graph representation.

    Raises ``ValueError`` on empty or malformed input.
    """
    if not dsl_strings:
        raise ValueError("DSL input is empty — provide at least one topology string.")

    seen_nodes: dict[str, None] = {}  # ordered set
    all_edges: list[tuple[str, str]] = []

    for dsl in dsl_strings:
        layers = _parse_layers(dsl)
        _collect_nodes_and_edges(layers, seen_nodes, all_edges)

    # Build depends_on mapping
    nodes = list(seen_nodes)
    depends_on: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in all_edges:
        if src not in depends_on[dst]:
            depends_on[dst].append(src)

    return ParsedDSL(nodes=nodes, edges=all_edges, depends_on=depends_on)


def _parse_layers(dsl: str) -> list[list[str]]:
    """Parse a single DSL string into validated layers of node names."""
    dsl = dsl.strip()
    if not dsl:
        raise ValueError("DSL input is empty — provide at least one topology string.")

    layers: list[list[str]] = []
    for layer in dsl.split("->"):
        names = [n.strip() for n in layer.split(",")]
        for name in names:
            if not name:
                raise ValueError(
                    f"Empty node name found in DSL '{dsl}'. "
                    "Malformed input — check arrows and commas."
                )
        layers.append(names)
    return layers


def _register_layer_nodes(
    layers: list[list[str]],
    seen_nodes: dict[str, None],
) -> None:
    """Register all node names from layers into the seen set."""
    for layer in layers:
        for name in layer:
            if name not in seen_nodes:
                seen_nodes[name] = None


def _connect_adjacent_layers(
    layers: list[list[str]],
    all_edges: list[tuple[str, str]],
) -> None:
    """Create edges between each pair of adjacent layers."""
    for i in range(len(layers) - 1):
        for src in layers[i]:
            for dst in layers[i + 1]:
                edge = (src, dst)
                if edge not in all_edges:
                    all_edges.append(edge)


def _collect_nodes_and_edges(
    layers: list[list[str]],
    seen_nodes: dict[str, None],
    all_edges: list[tuple[str, str]],
) -> None:
    """Register nodes and create edges between adjacent layers."""
    _register_layer_nodes(layers, seen_nodes)
    _connect_adjacent_layers(layers, all_edges)
