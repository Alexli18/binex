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

@dataclass(frozen=True)
class PatternInfo:
    """Rich metadata for a scaffold pattern."""

    dsl: str
    description: str
    use_case: str
    category: str  # core | control | human | integration | agentic
    node_count: int
    tags: tuple[str, ...]


PATTERN_METADATA: dict[str, PatternInfo] = {
    # === Core Topologies ===
    "linear": PatternInfo(
        dsl="A -> B -> C",
        description="Sequential pipeline — each step feeds the next",
        use_case="ETL pipeline, step-by-step processing",
        category="core",
        node_count=3,
        tags=("simple", "sequential"),
    ),
    "fan-out": PatternInfo(
        dsl="planner -> researcher1, researcher2, researcher3",
        description="One node triggers multiple parallel workers",
        use_case="Parallel research, multi-source data gathering",
        category="core",
        node_count=4,
        tags=("parallel", "branching"),
    ),
    "fan-in": PatternInfo(
        dsl="source1, source2, source3 -> aggregator",
        description="Multiple sources merge into one aggregation node",
        use_case="Data aggregation, multi-source synthesis, ensemble voting",
        category="core",
        node_count=4,
        tags=("parallel", "aggregation"),
    ),
    "fan-out-fan-in": PatternInfo(
        dsl="planner -> r1, r2, r3 -> summarizer",
        description="Plan → parallel work → aggregate results",
        use_case="Research pipeline, map-reduce analysis",
        category="core",
        node_count=5,
        tags=("parallel", "common"),
    ),
    "diamond": PatternInfo(
        dsl="A -> B, C -> D",
        description="Fork into two paths, then merge",
        use_case="A/B testing, dual-perspective analysis",
        category="core",
        node_count=4,
        tags=("branching", "merge"),
    ),
    "multi-stage": PatternInfo(
        dsl="A -> B, C -> D, E -> F",
        description="Multiple independent parallel chains",
        use_case="Independent processing streams, microservices",
        category="core",
        node_count=6,
        tags=("parallel", "independent"),
    ),
    "map-reduce": PatternInfo(
        dsl="split -> worker1, worker2, worker3 -> reduce",
        description="Split data, process in parallel, reduce to result",
        use_case="Batch processing, distributed analysis",
        category="core",
        node_count=5,
        tags=("parallel", "distributed"),
    ),
    # === Workflow Control ===
    "chain-with-review": PatternInfo(
        dsl="draft -> review -> revise -> final",
        description="Create → review → revise loop",
        use_case="Content writing, document review cycles, self-improvement loops",
        category="control",
        node_count=4,
        tags=("review", "iterative"),
    ),
    "pipeline-with-validation": PatternInfo(
        dsl="input -> process -> validate -> output",
        description="Process with a validation gate before output",
        use_case="Data quality checks, output validation",
        category="control",
        node_count=4,
        tags=("validation", "quality"),
    ),
    "conditional-routing": PatternInfo(
        dsl="classifier -> premium_handler, standard_handler -> reporter",
        description="Classify input, route to different handlers",
        use_case="Ticket routing, tiered processing, meta-controller dispatch",
        category="control",
        node_count=4,
        tags=("routing", "conditional"),
    ),
    "error-handling": PatternInfo(
        dsl="setup -> risky -> cleanup",
        description="Pipeline with error handling and cleanup",
        use_case="Operations that need cleanup on failure",
        category="control",
        node_count=3,
        tags=("errors", "resilience"),
    ),
    # === Human-in-the-Loop ===
    "human-approval": PatternInfo(
        dsl="draft -> approve -> publish",
        description="Content goes through human approval gate",
        use_case="Publishing workflows, deployment gates",
        category="human",
        node_count=3,
        tags=("approval", "gate"),
    ),
    "human-feedback": PatternInfo(
        dsl="generate -> human-review -> revise -> output",
        description="AI generates, human reviews, AI revises",
        use_case="AI-assisted writing, iterative refinement",
        category="human",
        node_count=4,
        tags=("feedback", "iterative"),
    ),
    # === Integration ===
    "a2a-multi-agent": PatternInfo(
        dsl="coordinator -> researcher -> reviewer",
        description="Orchestrate remote agents via A2A protocol",
        use_case="Multi-service agent coordination",
        category="integration",
        node_count=3,
        tags=("a2a", "remote"),
    ),
    "research": PatternInfo(
        dsl="planner -> researcher1, researcher2 -> validator -> summarizer",
        description="Plan → parallel research → validate → summarize",
        use_case="Deep research, competitive analysis",
        category="integration",
        node_count=5,
        tags=("research", "common"),
    ),
    "secure-pipeline": PatternInfo(
        dsl="fetcher -> processor -> writer",
        description="Fetch → process → write with env-based secrets",
        use_case="Secure data pipelines, API integrations",
        category="integration",
        node_count=3,
        tags=("security", "secrets"),
    ),
    "multi-provider": PatternInfo(
        dsl="planner -> researcher -> summarizer",
        description="Each node uses a different LLM provider",
        use_case="Best-of-breed model selection, cost optimization",
        category="integration",
        node_count=3,
        tags=("multi-model", "providers"),
    ),
    # === Agentic ===
    "reflection": PatternInfo(
        dsl="generator -> critic -> refiner",
        description="Agent critiques its own output and self-improves",
        use_case="Code review, essay improvement, self-correction",
        category="agentic",
        node_count=3,
        tags=("self-critique", "iterative"),
    ),
    "plan-execute-verify": PatternInfo(
        dsl="planner -> executor -> verifier",
        description="Decompose task → execute plan → verify result",
        use_case="Complex task solving, multi-step reasoning",
        category="agentic",
        node_count=3,
        tags=("planning", "verification"),
    ),
    "dry-run-harness": PatternInfo(
        dsl="agent -> simulator -> approve -> executor",
        description="Simulate first, human approves, then execute for real",
        use_case="Safe deployments, risky operations, production changes",
        category="agentic",
        node_count=4,
        tags=("simulation", "safety"),
    ),
}

# Backward-compatible flat dict: name → DSL string.
PATTERNS: dict[str, str] = {k: v.dsl for k, v in PATTERN_METADATA.items()}


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
