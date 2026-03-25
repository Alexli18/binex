"""Pattern template registry and expansion entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from binex.patterns.templates.critic import expand_critic

if TYPE_CHECKING:
    from binex.models.workflow import NodeSpec
    from binex.patterns.models import PatternSpec

ExpandResult = tuple[list["NodeSpec"], list[tuple[str, str]], list[dict]]

TEMPLATE_REGISTRY: dict[str, Callable] = {
    "critic": expand_critic,
}


def expand_pattern(spec: "PatternSpec") -> ExpandResult:
    """Expand a pattern spec into nodes, edges, and back_edges."""
    fn = TEMPLATE_REGISTRY.get(spec.pattern)
    if fn is None:
        raise ValueError(f"No template for pattern: {spec.pattern}")
    return fn(spec)
