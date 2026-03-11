"""Human interaction adapters — approval gate and free-text input."""

from __future__ import annotations

from uuid import uuid4

import click

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import TaskNode


class HumanApprovalAdapter:
    """Adapter that prompts a human to approve or reject input artifacts.

    On reject, collects feedback text (single-line or multiline).
    Returns decision artifact ('approved'/'rejected') and optional feedback artifact.
    """

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        self._display_artifacts(task, input_artifacts)

        answer = click.prompt(
            "  [a]pprove · [r]eject with feedback",
            type=click.Choice(["a", "r"]),
            show_choices=False,
        )

        derived = [a.id for a in input_artifacts]

        if answer == "a":
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

        # Reject — collect feedback
        feedback_text = self._collect_feedback()
        artifacts = [
            Artifact(
                id=f"art_{uuid4().hex[:12]}",
                run_id=task.run_id,
                type="decision",
                content="rejected",
                lineage=Lineage(produced_by=task.node_id, derived_from=derived),
            ),
            Artifact(
                id=f"art_{uuid4().hex[:12]}",
                run_id=task.run_id,
                type="feedback",
                content=feedback_text,
                lineage=Lineage(produced_by=task.node_id, derived_from=derived),
            ),
        ]
        return ExecutionResult(artifacts=artifacts)

    @staticmethod
    def _display_artifacts(task: TaskNode, input_artifacts: list[Artifact]) -> None:
        """Display input artifacts for review, using Rich if available."""
        click.echo()
        try:
            from rich.markdown import Markdown

            from binex.cli.ui import get_console, make_panel

            console = get_console()
            for art in input_artifacts:
                content = art.content if isinstance(art.content, str) else str(art.content)
                node = art.lineage.produced_by if art.lineage else "?"
                console.print(make_panel(
                    Markdown(content),
                    title=f"[bold]{node}[/bold] / {art.type}",
                    subtitle=f"Review node: {task.node_id}",
                ))
        except ImportError:
            click.echo(
                f"--- Human review required for node '{task.node_id}' ---",
                err=True,
            )
            for art in input_artifacts:
                click.echo(f"  [{art.id}] ({art.type}): {art.content}", err=True)

    @staticmethod
    def _collect_feedback() -> str:
        """Collect feedback: single-line or multiline ('m' to switch)."""
        text = click.prompt("  Feedback (or 'm' for multiline)")
        if text.strip().lower() != "m":
            return text

        click.echo("  Enter feedback (empty line to finish):")
        lines: list[str] = []
        while True:
            line = input("  > ")
            if not line:
                break
            lines.append(line)
        return "\n".join(lines)

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
    ) -> ExecutionResult:
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
