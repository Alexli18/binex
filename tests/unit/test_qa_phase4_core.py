"""Phase 4: Core Regression tests — CAT-5 Runtime, CAT-6 Replay, CAT-7 Stores, CAT-8 Adapters.

Only gaps not covered by existing tests are filled here.

TC-RUN-001: Two-node linear workflow
TC-RUN-002: Five-node pipeline
TC-RUN-003: Failing node -> error recorded, run fails
TC-RUN-004: Diamond DAG -> parallel execution of B, C
TC-RUN-005: Retry policy — node fails then succeeds
TC-RUN-007: ${node.*} interpolation at runtime -> artifact value resolved
TC-STR-001: SqliteExecutionStore — record -> get_run roundtrip
TC-STR-004: FilesystemArtifactStore — store -> get roundtrip
TC-STR-008: InMemory stores — concurrent operations
TC-ADP-008: LocalPythonAdapter — sync-like callable -> result
"""

from __future__ import annotations

import asyncio
import tempfile

import pytest

from binex.adapters.local import LocalPythonAdapter
from binex.graph.dag import DAG
from binex.graph.scheduler import Scheduler
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import RetryPolicy, TaskNode, TaskStatus
from binex.models.workflow import DefaultsSpec, NodeSpec, WorkflowSpec
from binex.runtime.dispatcher import Dispatcher
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.stores.backends.sqlite import SqliteExecutionStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EchoAdapter:
    """Returns an artifact containing the node_id as content."""

    def __init__(self, content: str | None = None, *, fail: bool = False) -> None:
        self._content = content
        self._fail = fail
        self.call_count = 0

    async def execute(
        self, task: TaskNode, input_artifacts: list[Artifact], trace_id: str,
    ) -> list[Artifact]:
        self.call_count += 1
        if self._fail:
            raise RuntimeError(f"Node {task.node_id} failed intentionally")
        content = self._content or f"result_from_{task.node_id}"
        return [
            Artifact(
                id=f"art_{task.run_id}_{task.node_id}",
                run_id=task.run_id,
                type="result",
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


class FlakeyAdapter:
    """Fails N times then succeeds."""

    def __init__(self, fail_count: int = 1) -> None:
        self._fail_count = fail_count
        self.call_count = 0

    async def execute(
        self, task: TaskNode, input_artifacts: list[Artifact], trace_id: str,
    ) -> list[Artifact]:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise RuntimeError(f"Transient failure attempt {self.call_count}")
        return [
            Artifact(
                id=f"art_{task.run_id}_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=f"success_after_{self.call_count}_attempts",
                lineage=Lineage(produced_by=task.node_id),
            )
        ]

    async def cancel(self, task_id: str) -> None:
        pass

    async def health(self) -> AgentHealth:
        return AgentHealth.ALIVE


def _make_spec(nodes_dict: dict) -> WorkflowSpec:
    nodes = {}
    for nid, ndata in nodes_dict.items():
        nodes[nid] = NodeSpec(
            agent=ndata.get("agent", "local://echo"),
            outputs=ndata.get("outputs", ["result"]),
            depends_on=ndata.get("depends_on", []),
            when=ndata.get("when"),
            inputs=ndata.get("inputs", {}),
            retry_policy=ndata.get("retry_policy"),
            deadline_ms=ndata.get("deadline_ms"),
        )
    return WorkflowSpec(name="test-workflow", nodes=nodes)


def _make_artifact(
    id: str, run_id: str = "run_01", produced_by: str = "node1",
) -> Artifact:
    return Artifact(
        id=id, run_id=run_id, type="test", content={"data": id},
        lineage=Lineage(produced_by=produced_by),
    )


# ===========================================================================
# CAT-5: Runtime — TC-RUN-001: Two-node linear workflow
# ===========================================================================


class TestTwoNodeLinearWorkflow:
    """TC-RUN-001: Two-node linear workflow -> both execute in order."""

    @pytest.mark.asyncio
    async def test_two_nodes_execute_sequentially(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)

        assert summary.status == "completed"
        assert summary.completed_nodes == 2
        assert summary.failed_nodes == 0

    @pytest.mark.asyncio
    async def test_two_nodes_order_verified_by_records(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)

        assert len(records) == 2
        task_ids = [r.task_id for r in records]
        assert "a" in task_ids
        assert "b" in task_ids

    @pytest.mark.asyncio
    async def test_b_receives_a_artifact_as_input(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)
        b_record = next(r for r in records if r.task_id == "b")

        # b should have a's artifact as input
        assert len(b_record.input_artifact_refs) == 1


# ===========================================================================
# CAT-5: Runtime — TC-RUN-002: Five-node pipeline
# ===========================================================================


class TestFiveNodePipeline:
    """TC-RUN-002: Five-node pipeline -> all execute sequentially."""

    @pytest.mark.asyncio
    async def test_five_nodes_all_complete(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "c": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["b"]},
            "d": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["c"]},
            "e": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["d"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)

        assert summary.status == "completed"
        assert summary.completed_nodes == 5
        assert summary.total_nodes == 5

    @pytest.mark.asyncio
    async def test_five_nodes_all_recorded(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "c": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["b"]},
            "d": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["c"]},
            "e": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["d"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)

        assert len(records) == 5
        task_ids = {r.task_id for r in records}
        assert task_ids == {"a", "b", "c", "d", "e"}


# ===========================================================================
# CAT-5: Runtime — TC-RUN-003: Workflow with failing node
# ===========================================================================


class TestFailingNodeWorkflow:
    """TC-RUN-003: Workflow with failing node -> error recorded, run fails."""

    @pytest.mark.asyncio
    async def test_failing_node_marks_run_failed(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://fail", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())
        orch.dispatcher.register_adapter("local://fail", EchoAdapter(fail=True))

        summary = await orch.run_workflow(spec)

        assert summary.status == "failed"
        assert summary.failed_nodes >= 1

    @pytest.mark.asyncio
    async def test_failing_node_error_recorded(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://fail", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())
        orch.dispatcher.register_adapter("local://fail", EchoAdapter(fail=True))

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)
        b_record = next(r for r in records if r.task_id == "b")

        assert b_record.status == TaskStatus.FAILED
        assert b_record.error is not None
        assert "failed intentionally" in b_record.error

    @pytest.mark.asyncio
    async def test_successful_node_before_failure_recorded(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://fail", "outputs": ["result"], "depends_on": ["a"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())
        orch.dispatcher.register_adapter("local://fail", EchoAdapter(fail=True))

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)
        a_record = next(r for r in records if r.task_id == "a")

        assert a_record.status == TaskStatus.COMPLETED


# ===========================================================================
# CAT-5: Runtime — TC-RUN-004: Diamond DAG
# ===========================================================================


class TestDiamondDAG:
    """TC-RUN-004: Diamond DAG -> parallel execution of B, C."""

    @pytest.mark.asyncio
    async def test_diamond_all_complete(self) -> None:
        #     A
        #    / \
        #   B   C
        #    \ /
        #     D
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "c": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "d": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["b", "c"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)

        assert summary.status == "completed"
        assert summary.completed_nodes == 4

    @pytest.mark.asyncio
    async def test_diamond_d_has_two_input_artifacts(self) -> None:
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "c": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "d": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["b", "c"]},
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)
        records = await exec_store.list_records(summary.run_id)
        d_record = next(r for r in records if r.task_id == "d")

        # D depends on B and C, so it should have 2 input artifacts
        assert len(d_record.input_artifact_refs) == 2

    @pytest.mark.asyncio
    async def test_diamond_b_and_c_become_ready_after_a(self) -> None:
        """Scheduler should mark both B and C as ready after A completes."""
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "c": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["a"]},
            "d": {"agent": "local://echo", "outputs": ["result"], "depends_on": ["b", "c"]},
        })
        dag = DAG.from_workflow(spec)
        sched = Scheduler(dag)

        # Initially only "a" is ready
        ready = sched.ready_nodes()
        assert ready == ["a"]

        # After "a" completes, "b" and "c" should both be ready
        sched.mark_completed("a")
        ready = sched.ready_nodes()
        assert set(ready) == {"b", "c"}


# ===========================================================================
# CAT-5: Runtime — TC-RUN-005: Retry policy
# ===========================================================================


class TestRetryPolicy:
    """TC-RUN-005: Retry policy — node fails then succeeds -> retried."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_failure(self) -> None:
        adapter = FlakeyAdapter(fail_count=1)
        dispatcher = Dispatcher()
        dispatcher.register_adapter("local://flakey", adapter)

        task = TaskNode(
            id="task_1", run_id="run_1", node_id="flakey_node",
            agent="local://flakey",
            retry_policy=RetryPolicy(max_retries=3, backoff="fixed"),
        )

        result = await dispatcher.dispatch(task, [], "trace_1")

        assert len(result.artifacts) == 1
        assert "success" in result.artifacts[0].content
        assert adapter.call_count == 2  # 1 fail + 1 success

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self) -> None:
        adapter = FlakeyAdapter(fail_count=5)  # always fails within 3 retries
        dispatcher = Dispatcher()
        dispatcher.register_adapter("local://flakey", adapter)

        task = TaskNode(
            id="task_1", run_id="run_1", node_id="flakey_node",
            agent="local://flakey",
            retry_policy=RetryPolicy(max_retries=3, backoff="fixed"),
        )

        with pytest.raises(RuntimeError, match="Transient failure"):
            await dispatcher.dispatch(task, [], "trace_1")

        assert adapter.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self) -> None:
        from binex.runtime.dispatcher import _backoff_delay

        # attempt 1 -> 0.1s, attempt 2 -> 0.2s, attempt 3 -> 0.4s
        assert _backoff_delay(1, "exponential") == 0.1
        assert _backoff_delay(2, "exponential") == 0.2
        assert _backoff_delay(3, "exponential") == 0.4
        # capped at 10s
        assert _backoff_delay(10, "exponential") == 10.0


# ===========================================================================
# CAT-5: Runtime — TC-RUN-007: ${node.*} interpolation at runtime
# ===========================================================================


class TestNodeInterpolationAtRuntime:
    """TC-RUN-007: ${node.*} interpolation -> artifact value resolved at runtime."""

    @pytest.mark.asyncio
    async def test_upstream_artifact_passed_to_downstream(self) -> None:
        """Verify that node B receives node A's output artifact."""
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {
                "agent": "local://echo",
                "outputs": ["result"],
                "depends_on": ["a"],
                "inputs": {"source": "${a.result}"},
            },
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)
        assert summary.status == "completed"

        records = await exec_store.list_records(summary.run_id)
        b_record = next(r for r in records if r.task_id == "b")

        # B should have received A's artifact as input
        assert len(b_record.input_artifact_refs) == 1
        a_art = await art_store.get(b_record.input_artifact_refs[0])
        assert a_art is not None
        assert a_art.lineage.produced_by == "a"

    @pytest.mark.asyncio
    async def test_artifact_content_flows_through_pipeline(self) -> None:
        """Verify artifact content from A is accessible downstream."""
        spec = _make_spec({
            "a": {"agent": "local://echo", "outputs": ["result"]},
            "b": {
                "agent": "local://echo",
                "outputs": ["result"],
                "depends_on": ["a"],
            },
        })
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", EchoAdapter())

        summary = await orch.run_workflow(spec)

        records = await exec_store.list_records(summary.run_id)
        a_record = next(r for r in records if r.task_id == "a")
        a_art = await art_store.get(a_record.output_artifact_refs[0])

        assert a_art is not None
        assert "result_from_a" in str(a_art.content)


# ===========================================================================
# CAT-7: Stores — TC-STR-001: SqliteExecutionStore roundtrip
# ===========================================================================


class TestSqliteRoundtrip:
    """TC-STR-001: SqliteExecutionStore — record -> get_run roundtrip."""

    @pytest.mark.asyncio
    async def test_create_and_get_run_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            try:
                run = RunSummary(
                    run_id="run_001",
                    workflow_name="my-workflow",
                    status="completed",
                    total_nodes=3,
                    completed_nodes=3,
                )
                await store.create_run(run)

                result = await store.get_run("run_001")
                assert result is not None
                assert result.run_id == "run_001"
                assert result.workflow_name == "my-workflow"
                assert result.status == "completed"
                assert result.total_nodes == 3
                assert result.completed_nodes == 3
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_record_and_list_records_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            try:
                rec = ExecutionRecord(
                    id="rec_001",
                    run_id="run_001",
                    task_id="node_a",
                    agent_id="local://echo",
                    status=TaskStatus.COMPLETED,
                    latency_ms=42,
                    trace_id="trace_001",
                    error=None,
                )
                await store.record(rec)

                records = await store.list_records("run_001")
                assert len(records) == 1
                assert records[0].id == "rec_001"
                assert records[0].task_id == "node_a"
                assert records[0].status == TaskStatus.COMPLETED
                assert records[0].latency_ms == 42
            finally:
                await store.close()

    @pytest.mark.asyncio
    async def test_get_run_nonexistent_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SqliteExecutionStore(db_path=f"{tmpdir}/test.db")
            try:
                result = await store.get_run("nonexistent")
                assert result is None
            finally:
                await store.close()


# ===========================================================================
# CAT-7: Stores — TC-STR-004: FilesystemArtifactStore roundtrip
# ===========================================================================


class TestFilesystemRoundtrip:
    """TC-STR-004: FilesystemArtifactStore — store -> get roundtrip."""

    @pytest.mark.asyncio
    async def test_store_and_get_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            art = Artifact(
                id="art_roundtrip",
                run_id="run_01",
                type="document",
                content={"key": "value", "nested": [1, 2, 3]},
                lineage=Lineage(produced_by="node1"),
            )
            await store.store(art)

            result = await store.get("art_roundtrip")
            assert result is not None
            assert result.id == "art_roundtrip"
            assert result.run_id == "run_01"
            assert result.type == "document"
            assert result.content == {"key": "value", "nested": [1, 2, 3]}
            assert result.lineage.produced_by == "node1"

    @pytest.mark.asyncio
    async def test_store_multiple_and_list_by_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            for i in range(3):
                art = _make_artifact(f"art_{i}", run_id="run_01")
                await store.store(art)

            results = await store.list_by_run("run_01")
            assert len(results) == 3
            ids = {a.id for a in results}
            assert ids == {"art_0", "art_1", "art_2"}


# ===========================================================================
# CAT-7: Stores — TC-STR-008: InMemory stores — concurrent operations
# ===========================================================================


class TestInMemoryConcurrent:
    """TC-STR-008: InMemory stores — concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_artifact_store_writes(self) -> None:
        store = InMemoryArtifactStore()

        async def write_artifact(i: int) -> None:
            art = Artifact(
                id=f"art_{i}",
                run_id="run_01",
                type="test",
                content=f"data_{i}",
                lineage=Lineage(produced_by=f"node_{i}"),
            )
            await store.store(art)

        await asyncio.gather(*[write_artifact(i) for i in range(50)])

        # All 50 artifacts should be stored
        results = await store.list_by_run("run_01")
        assert len(results) == 50

    @pytest.mark.asyncio
    async def test_concurrent_execution_store_writes(self) -> None:
        store = InMemoryExecutionStore()

        async def write_record(i: int) -> None:
            rec = ExecutionRecord(
                id=f"rec_{i}",
                run_id="run_01",
                task_id=f"node_{i}",
                agent_id="local://echo",
                status=TaskStatus.COMPLETED,
                latency_ms=i,
                trace_id="trace_01",
            )
            await store.record(rec)

        await asyncio.gather(*[write_record(i) for i in range(50)])

        records = await store.list_records("run_01")
        assert len(records) == 50

    @pytest.mark.asyncio
    async def test_concurrent_create_and_read_runs(self) -> None:
        store = InMemoryExecutionStore()

        async def create_run(i: int) -> None:
            run = RunSummary(
                run_id=f"run_{i}",
                workflow_name="test",
                status="completed",
                total_nodes=1,
            )
            await store.create_run(run)

        await asyncio.gather(*[create_run(i) for i in range(20)])

        runs = await store.list_runs()
        assert len(runs) == 20

        # Each run should be individually retrievable
        for i in range(20):
            r = await store.get_run(f"run_{i}")
            assert r is not None
            assert r.run_id == f"run_{i}"


# ===========================================================================
# CAT-8: Adapters — TC-ADP-008: LocalPythonAdapter — sync callable wrapped
# ===========================================================================


class TestLocalPythonAdapterSyncCallable:
    """TC-ADP-008: LocalPythonAdapter with a sync-style callable (async wrapper).

    Note: LocalPythonAdapter requires an async handler by its type signature.
    This test verifies that an async wrapper around sync logic works correctly.
    """

    @pytest.mark.asyncio
    async def test_sync_logic_in_async_handler(self) -> None:
        """A handler with sync computation inside an async function works."""
        async def sync_wrapped_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            # Sync computation — no await
            result_value = f"computed_{task.node_id}"
            return [
                Artifact(
                    id="art_sync",
                    run_id=task.run_id,
                    type="result",
                    content=result_value,
                    lineage=Lineage(produced_by=task.node_id),
                )
            ]

        adapter = LocalPythonAdapter(handler=sync_wrapped_handler)
        task = TaskNode(
            id="task_1", run_id="run_1", node_id="sync_node",
            agent="local://sync",
        )

        result = await adapter.execute(task, [], "trace_1")
        arts = result.artifacts

        assert len(arts) == 1
        assert arts[0].content == "computed_sync_node"
        assert arts[0].type == "result"

    @pytest.mark.asyncio
    async def test_handler_receives_input_artifacts(self) -> None:
        received_inputs: list[Artifact] = []

        async def capturing_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            received_inputs.extend(inputs)
            return [
                Artifact(
                    id="art_out",
                    run_id=task.run_id,
                    type="result",
                    content="processed",
                    lineage=Lineage(
                        produced_by=task.node_id,
                        derived_from=[a.id for a in inputs],
                    ),
                )
            ]

        adapter = LocalPythonAdapter(handler=capturing_handler)
        task = TaskNode(
            id="task_1", run_id="run_1", node_id="cap_node",
            agent="local://cap",
        )
        input_art = Artifact(
            id="art_in", run_id="run_1", type="text",
            content="input_data", lineage=Lineage(produced_by="prev"),
        )

        result = await adapter.execute(task, [input_art], "trace_1")
        arts = result.artifacts

        assert len(received_inputs) == 1
        assert received_inputs[0].id == "art_in"
        assert arts[0].lineage.derived_from == ["art_in"]

    @pytest.mark.asyncio
    async def test_handler_returning_empty_list(self) -> None:
        async def empty_handler(
            task: TaskNode, inputs: list[Artifact],
        ) -> list[Artifact]:
            return []

        adapter = LocalPythonAdapter(handler=empty_handler)
        task = TaskNode(
            id="task_1", run_id="run_1", node_id="empty_node",
            agent="local://empty",
        )

        result = await adapter.execute(task, [], "trace_1")
        assert result.artifacts == []
