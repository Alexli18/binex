"""QA Phase 5a: Security (CAT-13) + Integration/E2E (CAT-14) gap tests.

Covers test cases NOT already present in existing QA test files:
- TC-SEC-004: Path traversal — `/` blocked in run IDs and artifact IDs
- TC-SEC-005: Path traversal — `\\` blocked (Windows-style)
- TC-SEC-008: A2A adapter — validate response schema from agent endpoint
- TC-E2E-003: Diamond pattern → parallel fan-out + fan-in
- TC-E2E-004: Example YAML files — all 14 parse without error (stricter assertion)
- TC-E2E-006: Error handling workflow → retry + error recorded
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.adapters.a2a import A2AAgentAdapter
from binex.adapters.local import LocalPythonAdapter
from binex.models.artifact import Artifact, Lineage
from binex.models.task import RetryPolicy, TaskNode
from binex.runtime.orchestrator import Orchestrator
from binex.stores.backends.filesystem import FilesystemArtifactStore
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.workflow_spec.loader import load_workflow_from_string


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifact(
    id: str = "art_1",
    run_id: str = "run_1",
    produced_by: str = "node_1",
    content: str = "data",
    art_type: str = "result",
    derived_from: list[str] | None = None,
) -> Artifact:
    return Artifact(
        id=id,
        run_id=run_id,
        type=art_type,
        content=content,
        lineage=Lineage(produced_by=produced_by, derived_from=derived_from or []),
    )


def _make_task(**overrides) -> TaskNode:
    defaults = {
        "id": "task_1",
        "run_id": "run_1",
        "node_id": "node_1",
        "agent": "a2a://http://example.com",
    }
    defaults.update(overrides)
    return TaskNode(**defaults)


# ===========================================================================
# TC-SEC-004: Path traversal — `/` blocked in run IDs and artifact IDs
# ===========================================================================


class TestPathTraversalSlash:
    """TC-SEC-004: FilesystemArtifactStore must reject `/` in path components."""

    @pytest.mark.asyncio
    async def test_slash_in_artifact_id_rejected(self) -> None:
        """Artifact ID containing `/` must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            art = _make_artifact(id="etc/passwd")
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.store(art)

    @pytest.mark.asyncio
    async def test_slash_in_run_id_rejected(self) -> None:
        """Run ID containing `/` must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            art = _make_artifact(id="safe_art", run_id="run/evil")
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.store(art)

    @pytest.mark.asyncio
    async def test_get_with_slash_artifact_id_rejected(self) -> None:
        """get() with `/` in artifact_id must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.get("secret/file")

    @pytest.mark.asyncio
    async def test_list_by_run_with_slash_rejected(self) -> None:
        """list_by_run() with `/` in run_id must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.list_by_run("run/evil")

    @pytest.mark.asyncio
    async def test_absolute_path_in_artifact_id_rejected(self) -> None:
        """Artifact ID like `/etc/passwd` must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.get("/etc/passwd")


# ===========================================================================
# TC-SEC-005: Path traversal — `\` blocked (Windows-style)
# ===========================================================================


class TestPathTraversalBackslash:
    """TC-SEC-005: FilesystemArtifactStore must reject `\\` in path components."""

    @pytest.mark.asyncio
    async def test_backslash_in_artifact_id_rejected(self) -> None:
        """Artifact ID containing `\\` must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            art = _make_artifact(id="..\\etc\\passwd")
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.store(art)

    @pytest.mark.asyncio
    async def test_backslash_in_run_id_rejected(self) -> None:
        """Run ID containing `\\` must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            art = _make_artifact(id="safe", run_id="run\\evil")
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.store(art)

    @pytest.mark.asyncio
    async def test_get_with_backslash_rejected(self) -> None:
        """get() with `\\` in artifact_id must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.get("secret\\file")

    @pytest.mark.asyncio
    async def test_single_backslash_in_artifact_id_rejected(self) -> None:
        """Even a single backslash anywhere in the name is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FilesystemArtifactStore(base_path=tmpdir)
            with pytest.raises(ValueError, match="Invalid path component"):
                await store.get("name\\with\\slashes")


# ===========================================================================
# TC-SEC-008: A2A adapter — validate response schema from agent endpoint
# ===========================================================================


class TestA2AResponseSchemaValidation:
    """TC-SEC-008: Verify A2AAgentAdapter behavior with malformed responses."""

    @pytest.mark.asyncio
    async def test_empty_json_response_returns_empty_list(self) -> None:
        """Response with empty JSON `{}` (no 'artifacts' key) returns empty list."""
        adapter = A2AAgentAdapter(endpoint="http://example.com")
        task = _make_task()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await adapter.execute(task, [], "trace_1")

        assert result == []

    @pytest.mark.asyncio
    async def test_response_with_artifacts_missing_type_uses_unknown(self) -> None:
        """Artifact data without 'type' key defaults to 'unknown'."""
        adapter = A2AAgentAdapter(endpoint="http://example.com")
        task = _make_task()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"content": "some text"}],
        }

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await adapter.execute(task, [], "trace_1")

        assert len(result) == 1
        assert result[0].type == "unknown"
        assert result[0].content == "some text"

    @pytest.mark.asyncio
    async def test_response_with_non_json_body_raises(self) -> None:
        """Non-JSON response body should raise an error."""
        adapter = A2AAgentAdapter(endpoint="http://example.com")
        task = _make_task()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("bad", "", 0)

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            with pytest.raises(json.JSONDecodeError):
                await adapter.execute(task, [], "trace_1")

    @pytest.mark.asyncio
    async def test_response_with_artifacts_none_content(self) -> None:
        """Artifact data with content=None should be handled."""
        adapter = A2AAgentAdapter(endpoint="http://example.com")
        task = _make_task()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"type": "text", "content": None}],
        }

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await adapter.execute(task, [], "trace_1")

        assert len(result) == 1
        assert result[0].content is None

    @pytest.mark.asyncio
    async def test_response_lineage_tracks_input_artifacts(self) -> None:
        """Output artifacts should have derived_from pointing to input artifact IDs."""
        adapter = A2AAgentAdapter(endpoint="http://example.com")
        task = _make_task()
        input_art = _make_artifact(id="input_art_1")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "artifacts": [{"type": "text", "content": "output"}],
        }

        with patch("binex.adapters.a2a.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await adapter.execute(task, [input_art], "trace_1")

        assert len(result) == 1
        assert result[0].lineage.derived_from == ["input_art_1"]
        assert result[0].lineage.produced_by == "node_1"


# ===========================================================================
# TC-E2E-003: Diamond pattern → parallel fan-out + fan-in
# ===========================================================================


class TestDiamondPatternE2E:
    """TC-E2E-003: A diamond workflow (A -> B,C -> D) executes correctly."""

    @pytest.mark.asyncio
    async def test_diamond_workflow_completes(self) -> None:
        """Diamond: root -> left,right -> sink. All 4 nodes complete."""
        async def echo_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            content = {a.id: a.content for a in inputs} if inputs else {"msg": task.node_id}
            return [Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=content,
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )]

        adapter = LocalPythonAdapter(handler=echo_handler)
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", adapter)

        workflow = {
            "name": "diamond-test",
            "nodes": {
                "root": {"agent": "local://echo", "outputs": ["data"]},
                "left": {
                    "agent": "local://echo",
                    "outputs": ["left_out"],
                    "depends_on": ["root"],
                },
                "right": {
                    "agent": "local://echo",
                    "outputs": ["right_out"],
                    "depends_on": ["root"],
                },
                "sink": {
                    "agent": "local://echo",
                    "outputs": ["final"],
                    "depends_on": ["left", "right"],
                },
            },
        }

        summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 4
        assert summary.failed_nodes == 0
        assert summary.total_nodes == 4

    @pytest.mark.asyncio
    async def test_diamond_sink_receives_both_branches(self) -> None:
        """The sink node in a diamond receives artifacts from both branches."""
        received_inputs: list[list[Artifact]] = []

        async def tracking_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            received_inputs.append(inputs)
            return [Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content=f"from_{task.node_id}",
                lineage=Lineage(
                    produced_by=task.node_id,
                    derived_from=[a.id for a in inputs],
                ),
            )]

        adapter = LocalPythonAdapter(handler=tracking_handler)
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://echo", adapter)

        workflow = {
            "name": "diamond-inputs",
            "nodes": {
                "root": {"agent": "local://echo", "outputs": ["data"]},
                "left": {
                    "agent": "local://echo",
                    "outputs": ["left_out"],
                    "depends_on": ["root"],
                },
                "right": {
                    "agent": "local://echo",
                    "outputs": ["right_out"],
                    "depends_on": ["root"],
                },
                "sink": {
                    "agent": "local://echo",
                    "outputs": ["final"],
                    "depends_on": ["left", "right"],
                },
            },
        }

        summary = await orch.run_workflow(workflow)
        assert summary.status == "completed"

        # The sink node (last call) should have received 2 input artifacts
        # (one from left, one from right)
        sink_inputs = received_inputs[-1]
        sink_input_producers = {a.lineage.produced_by for a in sink_inputs}
        assert "left" in sink_input_producers
        assert "right" in sink_input_producers


# ===========================================================================
# TC-E2E-004: Example YAML files — all 14 parse without error (strict)
# ===========================================================================


EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


class TestAllExampleYAMLsStrict:
    """TC-E2E-004: All 20 example YAML files must parse as valid WorkflowSpecs."""

    def test_exactly_20_example_files_exist(self) -> None:
        """Verify the expected number of example YAML files."""
        yaml_files = sorted(EXAMPLES_DIR.glob("*.yaml"))
        assert len(yaml_files) == 21, (
            f"Expected 21 example YAML files, found {len(yaml_files)}: "
            f"{[f.name for f in yaml_files]}"
        )

    def test_all_examples_load_as_workflow_spec(self) -> None:
        """Every example YAML must load into a valid WorkflowSpec via the loader."""
        # Some examples reference ${env.*} vars; provide dummy values
        import os
        # Provide dummy values for all ${env.*} vars used in examples
        env_patch = {
            "API_KEY": "test-key",
            "API_ENDPOINT": "http://localhost:4000",
            "STORAGE_KEY": "test-storage-key",
        }
        yaml_files = sorted(EXAMPLES_DIR.glob("*.yaml"))
        failures: list[str] = []
        original_env = os.environ.copy()
        os.environ.update(env_patch)
        try:
            for path in yaml_files:
                try:
                    content = path.read_text()
                    spec = load_workflow_from_string(content, fmt="yaml")
                    assert spec.name, f"{path.name}: spec.name is empty"
                    assert len(spec.nodes) > 0, f"{path.name}: spec has no nodes"
                except Exception as exc:
                    failures.append(f"{path.name}: {exc}")
        finally:
            for key in env_patch:
                if key not in original_env:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_env[key]

        assert not failures, (
            f"Failed to parse {len(failures)} example(s):\n"
            + "\n".join(failures)
        )

    def test_all_examples_have_valid_agent_prefixes(self) -> None:
        """Every node agent must use a known prefix (local://, llm://, a2a://, human://)."""
        import os
        env_patch = {
            "API_KEY": "test-key",
            "API_ENDPOINT": "http://localhost:4000",
            "STORAGE_KEY": "test-storage-key",
        }
        known_prefixes = ("local://", "llm://", "a2a://", "human://")
        yaml_files = sorted(EXAMPLES_DIR.glob("*.yaml"))
        violations: list[str] = []
        original_env = os.environ.copy()
        os.environ.update(env_patch)
        try:
            for path in yaml_files:
                content = path.read_text()
                spec = load_workflow_from_string(content, fmt="yaml")
                for node_id, node in spec.nodes.items():
                    if not node.agent.startswith(known_prefixes):
                        violations.append(
                            f"{path.name}/{node_id}: unknown prefix in '{node.agent}'"
                        )
        finally:
            for key in env_patch:
                if key not in original_env:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_env[key]

        assert not violations, (
            f"Found {len(violations)} unknown agent prefix(es):\n"
            + "\n".join(violations)
        )


# ===========================================================================
# TC-E2E-006: Error handling workflow → retry + error recorded
# ===========================================================================


class TestErrorHandlingRetryE2E:
    """TC-E2E-006: A workflow with a failing node that has retry policy
    should attempt retries and record the error in execution records."""

    @pytest.mark.asyncio
    async def test_retry_then_fail_records_error(self) -> None:
        """Node fails after retries; error is recorded in execution store."""
        call_count = 0

        async def failing_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"attempt_{call_count}_failed")

        adapter = LocalPythonAdapter(handler=failing_handler)
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://flaky", adapter)

        workflow = {
            "name": "retry-test",
            "defaults": {
                "retry_policy": {"max_retries": 2, "backoff": "fixed"},
            },
            "nodes": {
                "step1": {
                    "agent": "local://flaky",
                    "outputs": ["result"],
                },
            },
        }

        summary = await orch.run_workflow(workflow)

        assert summary.status == "failed"
        assert summary.failed_nodes == 1

        # Verify execution record was persisted with an error message
        records = await exec_store.list_records(summary.run_id)
        assert len(records) == 1
        assert records[0].error is not None
        assert "failed" in records[0].error

    @pytest.mark.asyncio
    async def test_retry_then_succeed(self) -> None:
        """Node fails once then succeeds on retry — final status is completed."""
        call_count = 0

        async def flaky_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("transient error")
            return [Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content="success",
                lineage=Lineage(produced_by=task.node_id),
            )]

        adapter = LocalPythonAdapter(handler=flaky_handler)
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://flaky", adapter)

        workflow = {
            "name": "retry-success",
            "defaults": {
                "retry_policy": {"max_retries": 3, "backoff": "fixed"},
            },
            "nodes": {
                "step1": {
                    "agent": "local://flaky",
                    "outputs": ["result"],
                },
            },
        }

        with patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock):
            summary = await orch.run_workflow(workflow)

        assert summary.status == "completed"
        assert summary.completed_nodes == 1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_downstream_blocked_by_failed_node(self) -> None:
        """When upstream node fails, downstream node never executes."""
        async def failing_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            raise RuntimeError("permanent failure")

        async def echo_handler(task: TaskNode, inputs: list[Artifact]) -> list[Artifact]:
            return [Artifact(
                id=f"art_{task.node_id}",
                run_id=task.run_id,
                type="result",
                content="should not run",
                lineage=Lineage(produced_by=task.node_id),
            )]

        fail_adapter = LocalPythonAdapter(handler=failing_handler)
        echo_adapter = LocalPythonAdapter(handler=echo_handler)
        art_store = InMemoryArtifactStore()
        exec_store = InMemoryExecutionStore()
        orch = Orchestrator(art_store, exec_store)
        orch.dispatcher.register_adapter("local://fail", fail_adapter)
        orch.dispatcher.register_adapter("local://echo", echo_adapter)

        workflow = {
            "name": "blocked-downstream",
            "nodes": {
                "step1": {"agent": "local://fail", "outputs": ["data"]},
                "step2": {
                    "agent": "local://echo",
                    "outputs": ["result"],
                    "depends_on": ["step1"],
                },
            },
        }

        summary = await orch.run_workflow(workflow)

        assert summary.status == "failed"
        assert summary.failed_nodes >= 1
        # step2 should not have executed (it is blocked by step1's failure)
        assert summary.completed_nodes == 0
