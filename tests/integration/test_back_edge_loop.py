"""Integration test: full human review loop with back-edge."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from binex.adapters.human import HumanApprovalAdapter
from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import BackEdge, NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


async def _generate_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    feedback = [a for a in inputs if a.type == "feedback"]
    if feedback:
        content = f"revised based on: {feedback[0].content}"
    else:
        content = "initial draft"
    return [
        Artifact(
            id=f"art_{task.node_id}_{task.run_id[-4:]}",
            run_id=task.run_id,
            type="result",
            content=content,
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in inputs],
            ),
        )
    ]


async def _output_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
    return [
        Artifact(
            id=f"art_output",
            run_id=task.run_id,
            type="result",
            content=f"final: {inputs[0].content}" if inputs else "empty",
            lineage=Lineage(
                produced_by=task.node_id,
                derived_from=[a.id for a in inputs],
            ),
        )
    ]


def _build_spec() -> WorkflowSpec:
    return WorkflowSpec(
        name="review-loop-test",
        nodes={
            "generate": NodeSpec(agent="local://generate", outputs=["result"]),
            "review": NodeSpec(
                agent="human://review",
                outputs=["result"],
                depends_on=["generate"],
                back_edge=BackEdge(
                    target="generate",
                    when="${review.decision} == rejected",
                    max_iterations=5,
                ),
            ),
            "output": NodeSpec(
                agent="local://output",
                outputs=["result"],
                depends_on=["review"],
            ),
        },
    )


def _build_orchestrator() -> tuple[Orchestrator, InMemoryArtifactStore]:
    art_store = InMemoryArtifactStore()
    exec_store = InMemoryExecutionStore()
    orch = Orchestrator(art_store, exec_store)
    orch.dispatcher.register_adapter(
        "local://generate", LocalPythonAdapter(handler=_generate_handler),
    )
    orch.dispatcher.register_adapter(
        "human://review", HumanApprovalAdapter(),
    )
    orch.dispatcher.register_adapter(
        "local://output", LocalPythonAdapter(handler=_output_handler),
    )
    return orch, art_store


class TestFullReviewLoop:
    @pytest.mark.asyncio
    async def test_approve_on_first_try(self) -> None:
        spec = _build_spec()
        orch, _ = _build_orchestrator()

        with patch("binex.adapters.human.click.prompt", return_value="a"), \
             patch("binex.adapters.human.click.echo"):
            summary = await orch.run_workflow(spec)

        assert summary.status == "completed"
        assert summary.completed_nodes == 3

    @pytest.mark.asyncio
    async def test_reject_then_approve(self) -> None:
        """Reject once with feedback, then approve on second iteration."""
        spec = _build_spec()
        orch, art_store = _build_orchestrator()

        # First call: reject with feedback. Second call: approve.
        prompt_responses = ["r", "fix the intro", "a"]
        with patch("binex.adapters.human.click.prompt", side_effect=prompt_responses), \
             patch("binex.adapters.human.click.echo"):
            summary = await orch.run_workflow(spec)

        assert summary.status == "completed"

        # Verify generate produced a revised draft (feedback was injected)
        arts = await art_store.list_by_run(summary.run_id)
        gen_arts = [a for a in arts if a.lineage and a.lineage.produced_by == "generate"]
        assert len(gen_arts) >= 1

        # The latest generate artifact should reference the feedback
        revised = [a for a in gen_arts if "revised" in str(a.content)]
        assert len(revised) >= 1
        assert "fix the intro" in str(revised[0].content)

    @pytest.mark.asyncio
    async def test_max_iterations_accept(self) -> None:
        spec = WorkflowSpec(
            name="test",
            nodes={
                "generate": NodeSpec(agent="local://generate", outputs=["result"]),
                "review": NodeSpec(
                    agent="human://review",
                    outputs=["result"],
                    depends_on=["generate"],
                    back_edge=BackEdge(
                        target="generate",
                        when="${review.decision} == rejected",
                        max_iterations=1,
                    ),
                ),
                "output": NodeSpec(
                    agent="local://output",
                    outputs=["result"],
                    depends_on=["review"],
                ),
            },
        )
        orch, _ = _build_orchestrator()

        # Reject, feedback, then max iterations -> accept
        prompt_responses = ["r", "notes", "a"]
        with patch("binex.adapters.human.click.prompt", side_effect=prompt_responses), \
             patch("binex.adapters.human.click.echo"), \
             patch("binex.runtime.orchestrator.click.prompt", return_value="a"):
            summary = await orch.run_workflow(spec)

        assert summary.status == "completed"
