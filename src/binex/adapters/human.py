"""Human interaction adapters — approval gate and free-text input."""

from __future__ import annotations

from uuid import uuid4

import click

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode


class HumanApprovalAdapter:
    """Adapter that prompts a human to approve or reject input artifacts."""

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        # Display input artifacts on stderr
        click.echo(
            f"\n--- Human approval required for node '{task.node_id}' ---",
            err=True,
        )
        for art in input_artifacts:
            click.echo(f"  [{art.id}] ({art.type}): {art.content}", err=True)

        # Prompt for approval
        answer = click.prompt(
            "Approve?",
            type=click.Choice(["y", "n"]),
        )

        content = "approved" if answer == "y" else "rejected"

        return [
            Artifact(
                id=f"art_{uuid4().hex[:12]}",
                run_id=task.run_id,
                type="decision",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in input_artifacts],
                ),
            )
        ]

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


class HumanInputAdapter:
    """Adapter that prompts a human for free-text input.

    Use ``human://input`` as the agent prefix in workflow YAML.
    The node's ``system_prompt`` field is displayed as the prompt message.
    """

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> list[Artifact]:
        # Show context from upstream artifacts
        click.echo(
            f"\n--- Human input required for node '{task.node_id}' ---",
            err=True,
        )
        if input_artifacts:
            click.echo("Context:", err=True)
            for art in input_artifacts:
                click.echo(
                    f"  [{art.id}] ({art.type}): {art.content}",
                    err=True,
                )

        # Use the system_prompt/prompt as the question
        prompt_text = task.system_prompt or "Enter your input"
        text = click.prompt(prompt_text)

        return [
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

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE
