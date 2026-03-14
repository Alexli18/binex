"""Web UI human interaction adapters.

These replace the CLI-based HumanApprovalAdapter and HumanInputAdapter
when workflows are executed through the Web UI. Instead of click.prompt(),
they publish SSE events and await browser responses via PendingPrompts.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode

logger = logging.getLogger(__name__)


class WebHumanApprovalAdapter:
    """Web UI adapter for human approval gates.

    Publishes a ``human:prompt_needed`` SSE event and waits for
    the browser to POST a response via ``/api/v1/runs/{run_id}/respond``.
    """

    def __init__(self, event_bus, pending_prompts) -> None:
        self._event_bus = event_bus
        self._pending = pending_prompts

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        prompt_id = f"prompt_{uuid4().hex[:12]}"

        # Serialize input artifacts for the browser
        artifacts_data = [
            {
                "id": a.id,
                "type": a.type,
                "content": a.content if isinstance(a.content, str) else str(a.content),
                "produced_by": a.lineage.produced_by if a.lineage else None,
            }
            for a in input_artifacts
        ]

        # Register and publish prompt
        self._pending.register(prompt_id, metadata={
            "run_id": task.run_id,
            "node_id": task.node_id,
            "prompt_type": "approval",
        })

        await self._event_bus.publish(task.run_id, {
            "type": "human:prompt_needed",
            "prompt_id": prompt_id,
            "prompt_type": "approval",
            "node_id": task.node_id,
            "message": "Review and approve output from upstream nodes",
            "artifacts": artifacts_data,
        })

        logger.info("Waiting for approval on node %s (prompt %s)", task.node_id, prompt_id)

        # Block until browser responds
        response = await self._pending.wait(prompt_id)
        action = response.get("action", "reject")
        feedback_text = response.get("text", "")

        derived = [a.id for a in input_artifacts]

        if action == "approve":
            artifacts = [
                Artifact(
                    id=f"art_{uuid4().hex[:12]}",
                    run_id=task.run_id,
                    type="decision",
                    content="approved",
                    lineage=Lineage(produced_by=task.node_id, derived_from=derived),
                )
            ]
            return ExecutionResult(artifacts=artifacts)

        # Reject — include feedback
        artifacts = [
            Artifact(
                id=f"art_{uuid4().hex[:12]}",
                run_id=task.run_id,
                type="decision",
                content="rejected",
                lineage=Lineage(produced_by=task.node_id, derived_from=derived),
            ),
        ]
        if feedback_text:
            artifacts.append(
                Artifact(
                    id=f"art_{uuid4().hex[:12]}",
                    run_id=task.run_id,
                    type="feedback",
                    content=feedback_text,
                    lineage=Lineage(produced_by=task.node_id, derived_from=derived),
                )
            )
        return ExecutionResult(artifacts=artifacts)

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


class WebHumanInputAdapter:
    """Web UI adapter for free-text human input.

    Publishes a ``human:prompt_needed`` SSE event with the system prompt
    and waits for the browser to POST a text response.
    """

    def __init__(self, event_bus, pending_prompts) -> None:
        self._event_bus = event_bus
        self._pending = pending_prompts

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        prompt_id = f"prompt_{uuid4().hex[:12]}"

        artifacts_data = [
            {
                "id": a.id,
                "type": a.type,
                "content": a.content if isinstance(a.content, str) else str(a.content),
                "produced_by": a.lineage.produced_by if a.lineage else None,
            }
            for a in input_artifacts
        ]

        prompt_text = task.system_prompt or "Enter your input"

        self._pending.register(prompt_id, metadata={
            "run_id": task.run_id,
            "node_id": task.node_id,
            "prompt_type": "input",
        })

        await self._event_bus.publish(task.run_id, {
            "type": "human:prompt_needed",
            "prompt_id": prompt_id,
            "prompt_type": "input",
            "node_id": task.node_id,
            "message": prompt_text,
            "artifacts": artifacts_data,
        })

        logger.info("Waiting for input on node %s (prompt %s)", task.node_id, prompt_id)

        response = await self._pending.wait(prompt_id)
        text = response.get("text", "")

        artifacts = [
            Artifact(
                id=f"art_{uuid4().hex[:12]}",
                run_id=task.run_id,
                type="human_input",
                content=text,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]
        return ExecutionResult(artifacts=artifacts)

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


class WebHumanOutputAdapter:
    """Web UI adapter for displaying workflow output to the user.

    Publishes a ``human:output`` SSE event with the collected results.
    Does NOT wait for user response — just displays and passes through.
    """

    def __init__(self, event_bus, pending_prompts) -> None:
        self._event_bus = event_bus
        self._pending = pending_prompts

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        label = task.system_prompt or "Workflow Output"

        artifacts_data = [
            {
                "id": a.id,
                "type": a.type,
                "content": a.content if isinstance(a.content, str) else str(a.content),
                "produced_by": a.lineage.produced_by if a.lineage else None,
            }
            for a in input_artifacts
        ]

        await self._event_bus.publish(task.run_id, {
            "type": "human:output",
            "node_id": task.node_id,
            "label": label,
            "artifacts": artifacts_data,
        })

        combined = []
        for a in input_artifacts:
            combined.append(a.content if isinstance(a.content, str) else str(a.content))

        artifacts = [
            Artifact(
                id=f"art_{uuid4().hex[:12]}",
                run_id=task.run_id,
                type="human_output",
                content="\n\n".join(combined),
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]
        return ExecutionResult(artifacts=artifacts)

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
