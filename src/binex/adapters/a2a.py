"""A2AAgentAdapter — communicates with A2A-compatible agents via HTTP."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord, ExecutionResult
from binex.models.task import TaskNode

if TYPE_CHECKING:
    from binex.gateway import Gateway
    from binex.gateway.router import RoutingHints


class A2AAgentAdapter:
    """Adapter for remote A2A-compatible agents.

    When *gateway* is provided, ``execute()`` routes through the gateway
    instead of making a direct HTTP call.  When *gateway* is ``None``
    (the default), the original direct-HTTP behaviour is preserved.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        gateway: Gateway | None = None,
        routing_hints: RoutingHints | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._gateway = gateway
        self._routing_hints = routing_hints

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        # ── Gateway-routed path ──────────────────────────────────────
        if self._gateway is not None:
            from binex.gateway.router import RoutingRequest

            req = RoutingRequest(
                agent_uri=f"a2a://{self._endpoint}",
                task_id=task.id,
                skill=task.node_id,
                trace_id=trace_id,
                artifacts=[
                    {"id": a.id, "type": a.type, "content": a.content}
                    for a in input_artifacts
                ],
                routing=self._routing_hints,
            )
            gw_result = await self._gateway.route(req)
            data = {
                "artifacts": gw_result.artifacts,
                "cost": gw_result.cost,
            }
            return self._build_result(task, input_artifacts, data)

        # ── Direct HTTP path (original behaviour) ────────────────────
        payload = {
            "task_id": task.id,
            "system_prompt": task.system_prompt,
            "trace_id": trace_id,
            "artifacts": [
                {"id": a.id, "type": a.type, "content": a.content}
                for a in input_artifacts
            ],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._endpoint}/execute",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return self._build_result(task, input_artifacts, data)

    def _build_result(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        data: dict,
    ) -> ExecutionResult:
        """Build an ExecutionResult from raw response data."""
        artifacts = [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type=art_data.get("type", "unknown"),
                content=art_data.get("content"),
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
            for art_data in data.get("artifacts", [])
        ]

        # Extract optional cost from response
        reported_cost = data.get("cost")
        if reported_cost is not None:
            source = "agent_report"
            cost_amount = float(reported_cost)
        else:
            source = "unknown"
            cost_amount = 0.0

        cost_record = CostRecord(
            id=f"cost_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            task_id=task.node_id,
            cost=cost_amount,
            source=source,
        )

        return ExecutionResult(artifacts=artifacts, cost=cost_record)

    async def cancel(self, task_id: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._endpoint}/cancel",
                json={"task_id": task_id},
                timeout=10.0,
            )

    async def health(self) -> AgentHealth:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._endpoint}/health",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return AgentHealth.ALIVE
                return AgentHealth.DEGRADED
        except Exception:
            return AgentHealth.DOWN


class A2AExternalGatewayAdapter:
    """Adapter that routes A2A requests through an external standalone gateway.

    Instead of embedding a Gateway instance, this adapter sends requests to
    a running gateway server via ``POST /route``.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        gateway_url: str,
        routing_hints: RoutingHints | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._gateway_url = gateway_url.rstrip("/")
        self._routing_hints = routing_hints

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        from binex.gateway.router import RoutingRequest

        req = RoutingRequest(
            agent_uri=f"a2a://{self._endpoint}",
            task_id=task.id,
            skill=task.node_id,
            trace_id=trace_id,
            artifacts=[
                {"id": a.id, "type": a.type, "content": a.content}
                for a in input_artifacts
            ],
            routing=self._routing_hints,
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._gateway_url}/route",
                json=req.model_dump(),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return self._build_result(task, input_artifacts, data)

    def _build_result(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        data: dict,
    ) -> ExecutionResult:
        """Build an ExecutionResult from gateway response data."""
        artifacts = [
            Artifact(
                id=f"art_{uuid.uuid4().hex[:12]}",
                run_id=task.run_id,
                type=art_data.get("type", "unknown"),
                content=art_data.get("content"),
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
            for art_data in data.get("artifacts", [])
        ]

        reported_cost = data.get("cost")
        if reported_cost is not None:
            source = "agent_report"
            cost_amount = float(reported_cost)
        else:
            source = "unknown"
            cost_amount = 0.0

        cost_record = CostRecord(
            id=f"cost_{uuid.uuid4().hex[:12]}",
            run_id=task.run_id,
            task_id=task.node_id,
            cost=cost_amount,
            source=source,
        )

        return ExecutionResult(artifacts=artifacts, cost=cost_record)

    async def cancel(self, task_id: str) -> None:
        """Cancel is not supported through external gateway."""
        pass

    async def health(self) -> AgentHealth:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._gateway_url}/health",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    return AgentHealth.ALIVE
                return AgentHealth.DEGRADED
        except Exception:
            return AgentHealth.DOWN
