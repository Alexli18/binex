"""QA tests for replay engine — edge cases and correctness (P1 plan).

TC-REP-001: Replay with non-existent from_step — should raise ValueError
TC-REP-002: Replay with agent_swaps for non-existent agent key — behavior
TC-REP-003: Replay cached artifacts correctly copied to new run — verify content
TC-REP-004: Replay forked_from and forked_at_step set in RunSummary
TC-REP-005: Replay of non-existent run_id — should raise ValueError
"""

from __future__ import annotations

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.adapters.local import LocalPythonAdapter
from binex.runtime.dispatcher import Dispatcher
from binex.runtime.replay import ReplayEngine
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore


@pytest.fixture
def exec_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


def _make_dispatcher() -> Dispatcher:
    """Create a dispatcher with echo adapters for local:// agents."""

    async def _handler(task, inputs):
        content = {a.id: a.content for a in inputs} if inputs else {"msg": "no input"}
        return [
            Artifact(
                id=f"art_{task.node_id}_{task.run_id}",
                run_id=task.run_id,
                type="result",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )
        ]

    dispatcher = Dispatcher()
    dispatcher.register_adapter("local://echo", LocalPythonAdapter(handler=_handler))
    dispatcher.register_adapter("local://new_agent", LocalPythonAdapter(handler=_handler))
    return dispatcher


@pytest.fixture
def sample_workflow_dict() -> dict:
    return {
        "name": "test-pipeline",
        "description": "A -> B -> C pipeline",
        "nodes": {
            "a": {
                "agent": "local://echo",
                "system_prompt": "produce",
                "inputs": {},
                "outputs": ["result_a"],
            },
            "b": {
                "agent": "local://echo",
                "system_prompt": "transform",
                "inputs": {"data": "${a.result_a}"},
                "outputs": ["result_b"],
                "depends_on": ["a"],
            },
            "c": {
                "agent": "local://echo",
                "system_prompt": "consume",
                "inputs": {"data": "${b.result_b}"},
                "outputs": ["result_c"],
                "depends_on": ["b"],
            },
        },
    }


async def _seed_run(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
    run_id: str = "run_original",
    workflow_name: str = "test-pipeline",
) -> RunSummary:
    """Seed stores with a completed 3-node run: a -> b -> c."""
    summary = RunSummary(
        run_id=run_id,
        workflow_name=workflow_name,
        status="completed",
        total_nodes=3,
        completed_nodes=3,
    )
    await exec_store.create_run(summary)

    art_a = Artifact(
        id=f"art_a_{run_id}", run_id=run_id, type="result_a",
        content={"val": "from_a"}, lineage=Lineage(produced_by="a"),
    )
    art_b = Artifact(
        id=f"art_b_{run_id}", run_id=run_id, type="result_b",
        content={"val": "from_b"},
        lineage=Lineage(produced_by="b", derived_from=[art_a.id]),
    )
    art_c = Artifact(
        id=f"art_c_{run_id}", run_id=run_id, type="result_c",
        content={"val": "from_c"},
        lineage=Lineage(produced_by="c", derived_from=[art_b.id]),
    )
    for art in [art_a, art_b, art_c]:
        await art_store.store(art)

    for node_id, agent, in_refs, out_refs in [
        ("a", "local://echo", [], [art_a.id]),
        ("b", "local://echo", [art_a.id], [art_b.id]),
        ("c", "local://echo", [art_b.id], [art_c.id]),
    ]:
        rec = ExecutionRecord(
            id=f"rec_{node_id}_{run_id}",
            run_id=run_id,
            task_id=node_id,
            agent_id=agent,
            status=TaskStatus.COMPLETED,
            input_artifact_refs=in_refs,
            output_artifact_refs=out_refs,
            latency_ms=100,
            trace_id="trace_001",
        )
        await exec_store.record(rec)

    return summary


# ---------------------------------------------------------------------------
# TC-REP-001: Replay with non-existent from_step — should raise ValueError
# ---------------------------------------------------------------------------


class TestReplayNonExistentFromStep:
    """TC-REP-001: Replaying from a step not in the workflow should error."""

    @pytest.mark.asyncio
    async def test_raises_value_error_for_missing_step(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        with pytest.raises(ValueError, match="not found in workflow"):
            await engine.replay(
                original_run_id="run_original",
                workflow=sample_workflow_dict,
                from_step="nonexistent_step",
            )

    @pytest.mark.asyncio
    async def test_raises_for_empty_string_step(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Empty string as from_step should also raise."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        with pytest.raises(ValueError, match="not found in workflow"):
            await engine.replay(
                original_run_id="run_original",
                workflow=sample_workflow_dict,
                from_step="",
            )

    @pytest.mark.asyncio
    async def test_no_new_run_created_on_invalid_step(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """When from_step is invalid, no new run should be persisted."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        with pytest.raises(ValueError):
            await engine.replay(
                original_run_id="run_original",
                workflow=sample_workflow_dict,
                from_step="nonexistent_step",
            )

        # Only the original run should exist
        runs = await exec_store.list_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run_original"


# ---------------------------------------------------------------------------
# TC-REP-002: Replay with agent_swaps for non-existent agent key
# ---------------------------------------------------------------------------


class TestReplayAgentSwapNonExistentKey:
    """TC-REP-002: agent_swaps referencing a node not in the workflow."""

    @pytest.mark.asyncio
    async def test_swap_for_nonexistent_node_is_ignored(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """An agent_swap for a node key not in the workflow should be silently ignored."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        # "z" does not exist in the workflow, should not cause an error
        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
            agent_swaps={"z": "local://new_agent"},
        )

        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_swap_for_cached_step_uses_original_agent(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """A swap targeting a cached (upstream) step should not affect the cached record."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        # Swap "a" but replay from "b" — "a" is cached, so the swap should not apply
        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
            agent_swaps={"a": "local://new_agent"},
        )

        records = await exec_store.list_records(result.run_id)
        a_record = next(r for r in records if r.task_id == "a")
        # Cached record retains the original agent
        assert a_record.agent_id == "local://echo"

    @pytest.mark.asyncio
    async def test_swap_applies_to_re_executed_step(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Swap for a re-executed step should use the swapped agent."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
            agent_swaps={"b": "local://new_agent"},
        )

        records = await exec_store.list_records(result.run_id)
        b_record = next(r for r in records if r.task_id == "b")
        assert b_record.agent_id == "local://new_agent"


# ---------------------------------------------------------------------------
# TC-REP-003: Replay cached artifacts correctly copied — verify content
# ---------------------------------------------------------------------------


class TestReplayCachedArtifactContent:
    """TC-REP-003: Upstream cached artifacts should be accessible with correct content."""

    @pytest.mark.asyncio
    async def test_cached_step_references_original_artifact_ids(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Cached execution records should reference the same artifact IDs as the original."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
        )

        records = await exec_store.list_records(result.run_id)
        a_record = next(r for r in records if r.task_id == "a")
        assert a_record.output_artifact_refs == ["art_a_run_original"]

    @pytest.mark.asyncio
    async def test_cached_artifact_content_matches_original(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """The artifact content referenced by cached records should match the original."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="c",
        )

        # Both "a" and "b" are cached
        records = await exec_store.list_records(result.run_id)
        a_record = next(r for r in records if r.task_id == "a")
        b_record = next(r for r in records if r.task_id == "b")

        art_a = await art_store.get(a_record.output_artifact_refs[0])
        art_b = await art_store.get(b_record.output_artifact_refs[0])

        assert art_a is not None
        assert art_a.content == {"val": "from_a"}
        assert art_b is not None
        assert art_b.content == {"val": "from_b"}

    @pytest.mark.asyncio
    async def test_re_executed_step_receives_cached_upstream_artifacts(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Re-executed steps should receive the cached upstream artifacts as inputs."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
        )

        records = await exec_store.list_records(result.run_id)
        b_record = next(r for r in records if r.task_id == "b")

        # "b" should reference the cached artifact from "a" as input
        assert "art_a_run_original" in b_record.input_artifact_refs

    @pytest.mark.asyncio
    async def test_cached_record_has_zero_latency(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Cached execution records should have latency_ms == 0."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="c",
        )

        records = await exec_store.list_records(result.run_id)
        cached_records = [r for r in records if r.task_id in ("a", "b")]
        for rec in cached_records:
            assert rec.latency_ms == 0


# ---------------------------------------------------------------------------
# TC-REP-004: Replay forked_from and forked_at_step set in RunSummary
# ---------------------------------------------------------------------------


class TestReplayForkMetadata:
    """TC-REP-004: RunSummary should record fork provenance."""

    @pytest.mark.asyncio
    async def test_forked_from_set(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
        )

        assert result.forked_from == "run_original"

    @pytest.mark.asyncio
    async def test_forked_at_step_set(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="c",
        )

        assert result.forked_at_step == "c"

    @pytest.mark.asyncio
    async def test_forked_run_has_unique_run_id(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
        )

        assert result.run_id != "run_original"
        assert result.run_id.startswith("run_")

    @pytest.mark.asyncio
    async def test_forked_run_persisted_in_store(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """The forked run summary should be persisted and retrievable."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
        )

        stored = await exec_store.get_run(result.run_id)
        assert stored is not None
        assert stored.forked_from == "run_original"
        assert stored.forked_at_step == "b"
        assert stored.status == "completed"
        assert stored.workflow_name == "test-pipeline"

    @pytest.mark.asyncio
    async def test_forked_run_completed_nodes_count(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """A successful replay should report all nodes as completed."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="b",
        )

        assert result.total_nodes == 3
        assert result.completed_nodes == 3
        assert result.failed_nodes == 0

    @pytest.mark.asyncio
    async def test_replay_from_first_step_still_sets_fork_metadata(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Even replaying from the first step should record fork provenance."""
        await _seed_run(exec_store, art_store)
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        result = await engine.replay(
            original_run_id="run_original",
            workflow=sample_workflow_dict,
            from_step="a",
        )

        assert result.forked_from == "run_original"
        assert result.forked_at_step == "a"


# ---------------------------------------------------------------------------
# TC-REP-005: Replay of non-existent run_id — should raise ValueError
# ---------------------------------------------------------------------------


class TestReplayNonExistentRunId:
    """TC-REP-005: Replaying a run that does not exist should raise."""

    @pytest.mark.asyncio
    async def test_raises_value_error_for_missing_run_id(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        with pytest.raises(ValueError, match="not found"):
            await engine.replay(
                original_run_id="run_does_not_exist",
                workflow=sample_workflow_dict,
                from_step="b",
            )

    @pytest.mark.asyncio
    async def test_raises_before_creating_new_run(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """No new run should be created when the original run_id is invalid."""
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        with pytest.raises(ValueError):
            await engine.replay(
                original_run_id="run_ghost",
                workflow=sample_workflow_dict,
                from_step="b",
            )

        runs = await exec_store.list_runs()
        assert len(runs) == 0

    @pytest.mark.asyncio
    async def test_raises_with_empty_run_id(
        self,
        exec_store: InMemoryExecutionStore,
        art_store: InMemoryArtifactStore,
        sample_workflow_dict: dict,
    ):
        """Empty string run_id should also raise ValueError."""
        engine = ReplayEngine(
            execution_store=exec_store,
            artifact_store=art_store,
            dispatcher=_make_dispatcher(),
        )

        with pytest.raises(ValueError, match="not found"):
            await engine.replay(
                original_run_id="",
                workflow=sample_workflow_dict,
                from_step="b",
            )
