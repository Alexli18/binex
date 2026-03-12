"""Tests for when-condition support: scheduler skipping, condition parsing, orchestrator integration, validation."""

from __future__ import annotations

import pytest

from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.back_edge import evaluate_when
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.workflow_spec.validator import validate_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeAdapter:
    """Fake AgentAdapter that returns artifacts with a fixed content value."""

    def __init__(self, content: str = "done") -> None:
        self._content = content

    async def execute(
        self, task: TaskNode, input_artifacts: list[Artifact], trace_id: str,
    ) -> list[Artifact]:
        return [_make_artifact(task.run_id, task.node_id, self._content)]

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


def _make_dag(nodes: dict[str, list[str]]) -> DAG:
    """Build a DAG from {node_id: [dep_ids]} mapping."""
    node_ids = set(nodes.keys())
    forward: dict[str, set[str]] = {n: set() for n in node_ids}
    backward: dict[str, set[str]] = {n: set() for n in node_ids}
    for nid, deps in nodes.items():
        for dep in deps:
            forward[dep].add(nid)
            backward[nid].add(dep)
    return DAG(nodes=node_ids, forward=forward, backward=backward)


def _make_artifact(run_id: str, node_id: str, content: str, art_type: str = "result") -> Artifact:
    return Artifact(
        id=f"{run_id}_{node_id}_out",
        run_id=run_id,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=node_id),
    )


def _make_spec(nodes_dict: dict) -> WorkflowSpec:
    """Build a WorkflowSpec from a simplified dict of node definitions."""
    nodes = {}
    for nid, ndata in nodes_dict.items():
        nodes[nid] = NodeSpec(
            agent=ndata.get("agent", "llm://test"),
            outputs=ndata.get("outputs", ["result"]),
            depends_on=ndata.get("depends_on", []),
            when=ndata.get("when"),
            inputs=ndata.get("inputs", {}),
        )
    return WorkflowSpec(name="test-workflow", nodes=nodes)


# ===========================================================================
# T003: Scheduler — _skipped support
# ===========================================================================


class TestSchedulerSkipped:
    def test_scheduler_mark_skipped(self):
        dag = _make_dag({"a": [], "b": ["a"]})
        sched = Scheduler(dag)
        sched.mark_skipped("a")
        assert "a" in sched._skipped

    def test_scheduler_ready_nodes_with_skipped(self):
        dag = _make_dag({"a": [], "b": ["a"]})
        sched = Scheduler(dag)
        # Before skipping a, b is not ready
        ready = sched.ready_nodes()
        assert "b" not in ready
        # Skip a -> b should become ready
        sched.mark_skipped("a")
        ready = sched.ready_nodes()
        assert "b" in ready

    def test_scheduler_is_complete_with_skipped(self):
        dag = _make_dag({"a": [], "b": ["a"]})
        sched = Scheduler(dag)
        sched.mark_skipped("a")
        sched.mark_completed("b")
        assert sched.is_complete()

    def test_scheduler_skipped_not_in_completed(self):
        dag = _make_dag({"a": [], "b": ["a"]})
        sched = Scheduler(dag)
        sched.mark_skipped("a")
        assert "a" not in sched._completed


# ===========================================================================
# T004: evaluate_when parser
# ===========================================================================


class TestEvaluateWhen:
    def test_evaluate_when_equals_true(self):
        arts = {"check": [_make_artifact("r1", "check", "yes")]}
        assert evaluate_when("${check.result} == yes", arts) is True

    def test_evaluate_when_equals_false(self):
        arts = {"check": [_make_artifact("r1", "check", "no")]}
        assert evaluate_when("${check.result} == yes", arts) is False

    def test_evaluate_when_not_equals(self):
        arts = {"check": [_make_artifact("r1", "check", "no")]}
        assert evaluate_when("${check.result} != yes", arts) is True

    def test_evaluate_when_missing_node(self):
        arts: dict[str, list[Artifact]] = {}
        assert evaluate_when("${check.result} == yes", arts) is False

    def test_evaluate_when_invalid_syntax(self):
        arts: dict[str, list[Artifact]] = {}
        with pytest.raises(ValueError, match="Invalid when"):
            evaluate_when("bad syntax", arts)


# ===========================================================================
# T005: Orchestrator integration — when conditions
# ===========================================================================


class TestOrchestratorWhenConditions:
    @pytest.mark.asyncio
    async def test_orchestrator_skips_when_false(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} == yes",
            },
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        # Register a fake adapter that returns "no" for check node
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="no"))
        summary = await orch.run_workflow(spec)
        assert summary.status == "completed"
        # "act" should have been skipped
        assert summary.completed_nodes + summary.skipped_nodes == len(spec.nodes)
        assert summary.skipped_nodes == 1

    @pytest.mark.asyncio
    async def test_orchestrator_runs_when_true(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} == yes",
            },
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="yes"))
        summary = await orch.run_workflow(spec)
        assert summary.status == "completed"
        # Both nodes should have executed
        assert summary.completed_nodes == 2

    @pytest.mark.asyncio
    async def test_orchestrator_no_when_runs_normally(self):
        spec = _make_spec({
            "a": {"agent": "llm://test", "outputs": ["result"]},
            "b": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["a"],
            },
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("llm://test", FakeAdapter(content="done"))
        summary = await orch.run_workflow(spec)
        assert summary.status == "completed"
        assert summary.completed_nodes == 2


# ===========================================================================
# T006: Validator — when condition validation
# ===========================================================================


class TestValidateWhenConditions:
    def test_validate_when_valid_syntax(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${check.result} == yes",
            },
        })
        errors = validate_workflow(spec)
        assert not errors

    def test_validate_when_invalid_syntax(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["check"],
                "when": "bad syntax",
            },
        })
        errors = validate_workflow(spec)
        assert any("when" in e.lower() or "syntax" in e.lower() for e in errors)

    def test_validate_when_unknown_node(self):
        spec = _make_spec({
            "act": {
                "agent": "llm://test",
                "outputs": ["result"],
                "when": "${ghost.result} == yes",
            },
        })
        errors = validate_workflow(spec)
        assert any("ghost" in e for e in errors)

    def test_validate_when_not_dependency(self):
        spec = _make_spec({
            "check": {"agent": "llm://test", "outputs": ["result"]},
            "other": {"agent": "llm://test", "outputs": ["result"]},
            "act": {
                "agent": "llm://test",
                "outputs": ["result"],
                "depends_on": ["check"],
                "when": "${other.result} == yes",
            },
        })
        errors = validate_workflow(spec)
        assert any("other" in e and "depends_on" in e for e in errors)
