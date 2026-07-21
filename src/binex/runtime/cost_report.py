"""Cost reporting for non-LLM nodes (issue #79).

Cloud STT bills per minute, TTS per character, image generation per request.
A ``local://`` / ``python://`` handler declares its own cost by accepting a
``report_cost`` parameter and calling it — the value flows into the same cost
records, aggregations, and budgets as token-based LLM cost (budgets already
operate on dollars, so enforcement is unchanged; only ingestion widens).
"""

from __future__ import annotations

import uuid

from binex.models.cost import CostRecord
from binex.models.task import TaskNode

# Convenience keyword -> billing unit.
_UNIT_KWARGS = {"seconds": "seconds", "characters": "characters", "requests": "requests"}


class CostReporter:
    """Captures a single declared cost for a node execution."""

    def __init__(self, task: TaskNode) -> None:
        self._task = task
        self.record: CostRecord | None = None

    def report(
        self,
        *,
        cost: float | None = None,
        unit: str | None = None,
        quantity: float | None = None,
        unit_price: float | None = None,
        currency: str = "USD",
        **unit_kwargs: float,
    ) -> None:
        """Declare this node's cost.

        Provide either an explicit ``cost`` in dollars, or a ``quantity`` and
        ``unit_price`` (cost is their product), optionally with a convenience
        unit keyword: ``report_cost(seconds=7200, unit_price=0.0001)``.
        """
        for kw, mapped_unit in _UNIT_KWARGS.items():
            if kw in unit_kwargs:
                unit = mapped_unit
                quantity = unit_kwargs[kw]
                break

        if cost is None and quantity is not None and unit_price is not None:
            cost = quantity * unit_price
        if cost is None:
            cost = 0.0

        self.record = CostRecord(
            id=f"cost_{uuid.uuid4().hex[:12]}",
            run_id=self._task.run_id,
            task_id=self._task.node_id,
            cost=float(cost),
            currency=currency,
            source="agent_report",
            unit=unit or "custom",
            quantity=quantity,
            unit_price=unit_price,
            provenance="declared",
        )
