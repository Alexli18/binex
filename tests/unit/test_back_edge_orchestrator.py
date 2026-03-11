"""Tests for orchestrator back-edge evaluation and feedback injection."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.artifact import Artifact, Lineage
from binex.models.workflow import BackEdge, NodeSpec, WorkflowSpec
from binex.runtime.orchestrator import Orchestrator, evaluate_when
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


def _make_spec_with_back_edge(max_iter: int = 3) -> WorkflowSpec:
    return WorkflowSpec(
        name="test",
        nodes={
            "generate": NodeSpec(
                agent="llm://test", outputs=["result"],
            ),
            "review": NodeSpec(
                agent="human://review",
                outputs=["result"],
                depends_on=["generate"],
                back_edge=BackEdge(
                    target="generate",
                    when="${review.decision} == rejected",
                    max_iterations=max_iter,
                ),
            ),
        },
    )


class TestEvaluateBackEdge:
    @pytest.mark.asyncio
    async def test_no_back_edge_does_nothing(self) -> None:
        spec = WorkflowSpec(
            name="test",
            nodes={
                "a": NodeSpec(agent="x", outputs=["o"]),
            },
        )
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        dag = DAG.from_workflow(spec)
        sched = Scheduler(dag)
        sched.mark_running("a")
        sched.mark_completed("a")
        node_artifacts = {"a": []}
        history: dict[str, list[list[Artifact]]] = {}
        await orch._evaluate_back_edge(
            spec, sched, dag, "a", node_artifacts, history,
        )
        # Nothing changed — a still completed
        assert "a" in sched._completed

    @pytest.mark.asyncio
    async def test_condition_not_met_continues_forward(self) -> None:
        spec = _make_spec_with_back_edge()
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        dag = DAG.from_workflow(spec)
        sched = Scheduler(dag)

        sched.mark_running("generate")
        sched.mark_completed("generate")
        sched.mark_running("review")
        sched.mark_completed("review")

        # Approved — condition "${review.decision} == rejected" is NOT met
        approved_art = Artifact(
            id="art_1", run_id="r", type="decision", content="approved",
            lineage=Lineage(produced_by="review"),
        )
        node_artifacts = {
            "generate": [],
            "review": [approved_art],
        }
        history: dict[str, list[list[Artifact]]] = {}
        await orch._evaluate_back_edge(
            spec, sched, dag, "review", node_artifacts, history,
        )
        # No reset — generate stays completed
        assert "generate" in sched._completed

    @pytest.mark.asyncio
    async def test_condition_met_resets_chain(self) -> None:
        spec = _make_spec_with_back_edge()
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        dag = DAG.from_workflow(spec)
        sched = Scheduler(dag)

        sched.mark_running("generate")
        sched.mark_completed("generate")
        sched.mark_running("review")
        sched.mark_completed("review")

        rejected_art = Artifact(
            id="art_1", run_id="r", type="decision", content="rejected",
            lineage=Lineage(produced_by="review"),
        )
        feedback_art = Artifact(
            id="art_2", run_id="r", type="feedback", content="fix intro",
            lineage=Lineage(produced_by="review"),
        )
        node_artifacts = {
            "generate": [Artifact(
                id="art_0", run_id="r", type="result", content="draft",
                lineage=Lineage(produced_by="generate"),
            )],
            "review": [rejected_art, feedback_art],
        }
        history: dict[str, list[list[Artifact]]] = {}
        await orch._evaluate_back_edge(
            spec, sched, dag, "review", node_artifacts, history,
        )
        # Both nodes reset
        assert "generate" not in sched._completed
        assert "review" not in sched._completed
        # Old artifacts moved to history
        assert len(history.get("generate", [])) == 1
        # Feedback injected for generate
        assert "generate" in orch._pending_feedback

    @pytest.mark.asyncio
    async def test_max_iterations_prompts_user_accept(self) -> None:
        spec = _make_spec_with_back_edge(max_iter=1)
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        dag = DAG.from_workflow(spec)
        sched = Scheduler(dag)

        # Simulate already executed once
        sched.mark_running("review")
        sched.mark_completed("review")
        sched.mark_pending_again("review")  # count = 1
        sched.mark_running("review")
        sched.mark_completed("review")

        rejected_art = Artifact(
            id="art_1", run_id="r", type="decision", content="rejected",
            lineage=Lineage(produced_by="review"),
        )
        node_artifacts = {"review": [rejected_art], "generate": []}
        history: dict[str, list[list[Artifact]]] = {}

        with patch("binex.runtime.orchestrator.click.prompt", return_value="a"):
            await orch._evaluate_back_edge(
                spec, sched, dag, "review", node_artifacts, history,
            )
        # Accepted — stays completed, no reset
        assert "review" in sched._completed

    @pytest.mark.asyncio
    async def test_max_iterations_prompts_user_fail(self) -> None:
        spec = _make_spec_with_back_edge(max_iter=1)
        orch = Orchestrator(InMemoryArtifactStore(), InMemoryExecutionStore())
        dag = DAG.from_workflow(spec)
        sched = Scheduler(dag)

        sched.mark_running("review")
        sched.mark_completed("review")
        sched.mark_pending_again("review")
        sched.mark_running("review")
        sched.mark_completed("review")

        rejected_art = Artifact(
            id="art_1", run_id="r", type="decision", content="rejected",
            lineage=Lineage(produced_by="review"),
        )
        node_artifacts = {"review": [rejected_art], "generate": []}
        history: dict[str, list[list[Artifact]]] = {}

        with patch("binex.runtime.orchestrator.click.prompt", return_value="f"):
            await orch._evaluate_back_edge(
                spec, sched, dag, "review", node_artifacts, history,
            )
        assert "review" in sched._failed
