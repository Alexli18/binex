"""Pattern template registry and expansion entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from binex.patterns.templates.best_of_n import expand_best_of_n
from binex.patterns.templates.chain_of_verification import expand_chain_of_verification
from binex.patterns.templates.constitutional import expand_constitutional
from binex.patterns.templates.critic import expand_critic
from binex.patterns.templates.debate import expand_debate
from binex.patterns.templates.fsm import expand_fsm
from binex.patterns.templates.plan_execute import expand_plan_execute
from binex.patterns.templates.reflexion import expand_reflexion
from binex.patterns.templates.scatter import expand_scatter

if TYPE_CHECKING:
    from binex.models.workflow import NodeSpec
    from binex.patterns.models import PatternSpec

ExpandResult = tuple[list["NodeSpec"], list[tuple[str, str]], list[dict]]

TEMPLATE_REGISTRY: dict[str, Callable] = {
    "critic": expand_critic,
    "debate": expand_debate,
    "best_of_n": expand_best_of_n,
    "reflexion": expand_reflexion,
    "scatter": expand_scatter,
    "fsm": expand_fsm,
    "constitutional": expand_constitutional,
    "chain_of_verification": expand_chain_of_verification,
    "plan_execute": expand_plan_execute,
}


def expand_pattern(spec: "PatternSpec") -> ExpandResult:
    """Expand a pattern spec into nodes, edges, and back_edges."""
    fn = TEMPLATE_REGISTRY.get(spec.pattern)
    if fn is None:
        raise ValueError(f"No template for pattern: {spec.pattern}")
    return fn(spec)
