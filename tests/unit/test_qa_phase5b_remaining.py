"""QA Phase 5b — remaining gap tests for CAT-2, CAT-9, CAT-10, CAT-11.

Coverage gap analysis:
- TC-REG-002: Duplicate agent registration (same explicit ID) — overwrite behavior
- TC-TRC-003: Lineage tree — circular derived_from regression (BUG-002)
- TC-WFS-003+: User variable interpolation verified in node inputs
- TC-WFS-006+: Explicit no-entry-node test (all nodes have deps, no cycle)
- TC-MDL-004: ExecutionRecord JSON roundtrip (model_dump / model_validate)
- TC-MDL-007: AgentInfo missing required fields raises ValidationError
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from binex.models.agent import AgentHealth, AgentInfo
from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import RetryPolicy, TaskStatus
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.registry.app import app, registry_state
from binex.stores.backends.memory import InMemoryArtifactStore
from binex.trace.lineage import build_lineage_tree
from binex.workflow_spec.loader import load_workflow_from_string
from binex.workflow_spec.validator import validate_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry():
    registry_state.agents.clear()
    yield
    registry_state.agents.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


# ===========================================================================
# CAT-2: TC-REG-002 — Duplicate agent registration
# ===========================================================================


class TestRegistryDuplicateRegistration:
    """TC-REG-002: POST /agents with same explicit ID overwrites previous entry."""

    def test_duplicate_id_overwrites_agent(self, client: TestClient) -> None:
        """Registering with same explicit ID should overwrite the existing agent."""
        payload_v1 = {
            "id": "agent-dup-001",
            "endpoint": "http://localhost:9001",
            "name": "Agent V1",
            "capabilities": ["plan"],
        }
        resp1 = client.post("/agents", json=payload_v1)
        assert resp1.status_code == 201
        assert resp1.json()["name"] == "Agent V1"

        payload_v2 = {
            "id": "agent-dup-001",
            "endpoint": "http://localhost:9002",
            "name": "Agent V2",
            "capabilities": ["plan", "research"],
        }
        resp2 = client.post("/agents", json=payload_v2)
        assert resp2.status_code == 201
        data = resp2.json()
        assert data["name"] == "Agent V2"
        assert data["endpoint"] == "http://localhost:9002"
        assert set(data["capabilities"]) == {"plan", "research"}

        # Only one agent should exist with that ID
        assert len(registry_state.agents) == 1
        assert registry_state.agents["agent-dup-001"].name == "Agent V2"

    def test_duplicate_auto_id_creates_separate_entries(self, client: TestClient) -> None:
        """Two registrations without explicit ID produce different auto-generated IDs."""
        payload = {
            "endpoint": "http://localhost:9001",
            "name": "Same Name",
            "capabilities": ["plan"],
        }
        resp1 = client.post("/agents", json=payload)
        resp2 = client.post("/agents", json=payload)
        assert resp1.status_code == 201
        assert resp2.status_code == 201

        id1 = resp1.json()["id"]
        id2 = resp2.json()["id"]
        # Auto-generated UUIDs should differ
        assert id1 != id2
        assert len(registry_state.agents) == 2

    def test_duplicate_id_preserves_health_default(self, client: TestClient) -> None:
        """Overwriting an agent resets health to default ALIVE."""
        payload = {
            "id": "agent-health-reset",
            "endpoint": "http://localhost:9001",
            "name": "Agent",
            "capabilities": [],
        }
        client.post("/agents", json=payload)
        # Manually set health to DOWN
        registry_state.agents["agent-health-reset"].health = AgentHealth.DOWN

        # Re-register: new AgentInfo is created with default ALIVE
        client.post("/agents", json=payload)
        assert registry_state.agents["agent-health-reset"].health == AgentHealth.ALIVE


# ===========================================================================
# CAT-9: TC-TRC-003 — Lineage tree circular reference regression (BUG-002)
# ===========================================================================


class TestLineageCircularRefRegression:
    """TC-TRC-003: build_lineage_tree handles circular derived_from without infinite loop."""

    @pytest.mark.asyncio
    async def test_self_referencing_artifact_returns_none_for_cycle(
        self, art_store: InMemoryArtifactStore
    ) -> None:
        """An artifact whose derived_from references itself should not cause infinite recursion."""
        art = Artifact(
            id="art_self",
            run_id="run_001",
            type="text",
            content="data",
            lineage=Lineage(produced_by="node_a", derived_from=["art_self"]),
        )
        await art_store.store(art)

        tree = await build_lineage_tree(art_store, "art_self")

        # The tree should exist for art_self, but the self-reference parent is skipped
        assert tree is not None
        assert tree["artifact_id"] == "art_self"
        assert tree["parents"] == []

    @pytest.mark.asyncio
    async def test_two_node_cycle_terminates(
        self, art_store: InMemoryArtifactStore
    ) -> None:
        """A -> B -> A cycle should terminate without infinite recursion."""
        art_a = Artifact(
            id="art_a",
            run_id="run_001",
            type="text",
            content="data_a",
            lineage=Lineage(produced_by="node_a", derived_from=["art_b"]),
        )
        art_b = Artifact(
            id="art_b",
            run_id="run_001",
            type="text",
            content="data_b",
            lineage=Lineage(produced_by="node_b", derived_from=["art_a"]),
        )
        await art_store.store(art_a)
        await art_store.store(art_b)

        tree = await build_lineage_tree(art_store, "art_a")

        assert tree is not None
        assert tree["artifact_id"] == "art_a"
        # art_b should appear as parent, but art_a (cycle) should be skipped in art_b's parents
        assert len(tree["parents"]) == 1
        assert tree["parents"][0]["artifact_id"] == "art_b"
        assert tree["parents"][0]["parents"] == []  # art_a cycle detected, skipped

    @pytest.mark.asyncio
    async def test_three_node_cycle_terminates(
        self, art_store: InMemoryArtifactStore
    ) -> None:
        """A -> B -> C -> A cycle should terminate without infinite recursion."""
        for art_id, parent_id in [("c_a", "c_b"), ("c_b", "c_c"), ("c_c", "c_a")]:
            art = Artifact(
                id=art_id,
                run_id="run_001",
                type="text",
                content=f"data_{art_id}",
                lineage=Lineage(produced_by=f"node_{art_id}", derived_from=[parent_id]),
            )
            await art_store.store(art)

        tree = await build_lineage_tree(art_store, "c_a")

        assert tree is not None
        assert tree["artifact_id"] == "c_a"
        # Should walk c_a -> c_b -> c_c, then c_c references c_a (ancestor) -> stops
        assert len(tree["parents"]) == 1  # c_b
        assert len(tree["parents"][0]["parents"]) == 1  # c_c
        assert tree["parents"][0]["parents"][0]["parents"] == []  # c_a is ancestor, skipped

    @pytest.mark.asyncio
    async def test_diamond_pattern_allows_repeated_node(
        self, art_store: InMemoryArtifactStore
    ) -> None:
        """Diamond pattern (A -> B, A -> C, B -> D, C -> D) should include D in both branches."""
        artifacts = [
            Artifact(id="d_root", run_id="r", type="t", content="r",
                     lineage=Lineage(produced_by="root", derived_from=[])),
            Artifact(id="d_left", run_id="r", type="t", content="l",
                     lineage=Lineage(produced_by="left", derived_from=["d_root"])),
            Artifact(id="d_right", run_id="r", type="t", content="r",
                     lineage=Lineage(produced_by="right", derived_from=["d_root"])),
            Artifact(id="d_merge", run_id="r", type="t", content="m",
                     lineage=Lineage(produced_by="merge", derived_from=["d_left", "d_right"])),
        ]
        for a in artifacts:
            await art_store.store(a)

        tree = await build_lineage_tree(art_store, "d_merge")

        assert tree is not None
        parent_ids = {p["artifact_id"] for p in tree["parents"]}
        assert parent_ids == {"d_left", "d_right"}
        # Both branches should reach d_root (diamond, not cycle)
        for parent in tree["parents"]:
            assert len(parent["parents"]) == 1
            assert parent["parents"][0]["artifact_id"] == "d_root"


# ===========================================================================
# CAT-10: TC-WFS-003 — User variable interpolation in node inputs
# ===========================================================================


class TestUserVarInterpolation:
    """TC-WFS-003: ${user.*} variables resolved in node inputs."""

    def test_user_var_substituted_in_input(self) -> None:
        """${user.topic} in inputs replaced with actual value."""
        yaml_str = """
name: test-interp
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      query: "Research about ${user.topic}"
    outputs: [result]
"""
        spec = load_workflow_from_string(yaml_str, user_vars={"topic": "quantum computing"})
        assert spec.nodes["step1"].inputs["query"] == "Research about quantum computing"

    def test_multiple_user_vars_substituted(self) -> None:
        """Multiple ${user.*} placeholders resolved in same input."""
        yaml_str = """
name: multi-var
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      query: "${user.verb} about ${user.topic}"
    outputs: [result]
"""
        spec = load_workflow_from_string(
            yaml_str, user_vars={"verb": "Summarize", "topic": "AI safety"}
        )
        assert spec.nodes["step1"].inputs["query"] == "Summarize about AI safety"

    def test_user_var_not_provided_remains_literal(self) -> None:
        """${user.missing} not in user_vars remains as literal string."""
        yaml_str = """
name: missing-var
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      query: "${user.missing}"
    outputs: [result]
"""
        spec = load_workflow_from_string(yaml_str, user_vars={})
        assert spec.nodes["step1"].inputs["query"] == "${user.missing}"

    def test_user_var_in_nested_input(self) -> None:
        """${user.*} resolved inside nested dict inputs."""
        yaml_str = """
name: nested-var
nodes:
  step1:
    agent: llm://gpt-4
    inputs:
      config:
        api_key: "${user.key}"
    outputs: [result]
"""
        spec = load_workflow_from_string(yaml_str, user_vars={"key": "sk-123"})
        assert spec.nodes["step1"].inputs["config"]["api_key"] == "sk-123"


# ===========================================================================
# CAT-10: TC-WFS-006 — No entry node (all nodes have dependencies)
# ===========================================================================


class TestNoEntryNode:
    """TC-WFS-006: Workflow where every node depends on another (no entry point)."""

    def test_all_nodes_have_deps_detected(self) -> None:
        """Validator should report 'no entry nodes' when all nodes have depends_on."""
        # Note: This also creates a cycle, but test the entry node message explicitly
        spec = WorkflowSpec(
            name="no-entry",
            nodes={
                "a": NodeSpec(agent="x", outputs=["o"], depends_on=["b"]),
                "b": NodeSpec(agent="x", outputs=["o"], depends_on=["a"]),
            },
        )
        errors = validate_workflow(spec)
        assert any("entry" in e.lower() for e in errors)

    def test_three_node_no_entry_detected(self) -> None:
        """Three-node graph with no entry is detected."""
        spec = WorkflowSpec(
            name="no-entry-3",
            nodes={
                "a": NodeSpec(agent="x", outputs=["o"], depends_on=["c"]),
                "b": NodeSpec(agent="x", outputs=["o"], depends_on=["a"]),
                "c": NodeSpec(agent="x", outputs=["o"], depends_on=["b"]),
            },
        )
        errors = validate_workflow(spec)
        has_entry_error = any("entry" in e.lower() for e in errors)
        has_cycle_error = any("cycle" in e.lower() for e in errors)
        assert has_entry_error or has_cycle_error


# ===========================================================================
# CAT-11: TC-MDL-004 — ExecutionRecord JSON roundtrip
# ===========================================================================


class TestExecutionRecordRoundtrip:
    """TC-MDL-004: ExecutionRecord serializes to dict/JSON and back without loss."""

    def test_model_dump_and_validate_roundtrip(self) -> None:
        """model_dump -> model_validate should preserve all fields."""
        original = ExecutionRecord(
            id="rec-rt-001",
            run_id="run-rt-001",
            task_id="planner",
            parent_task_id="root",
            agent_id="llm://gpt-4",
            status=TaskStatus.COMPLETED,
            input_artifact_refs=["art_in_1", "art_in_2"],
            output_artifact_refs=["art_out_1"],
            prompt="Plan the research",
            model="gpt-4",
            tool_calls=[{"name": "search", "args": {"q": "AI"}}],
            latency_ms=1500,
            trace_id="trace-rt-001",
            error=None,
        )

        dumped = original.model_dump()
        restored = ExecutionRecord.model_validate(dumped)

        assert restored.id == original.id
        assert restored.run_id == original.run_id
        assert restored.task_id == original.task_id
        assert restored.parent_task_id == original.parent_task_id
        assert restored.agent_id == original.agent_id
        assert restored.status == original.status
        assert restored.input_artifact_refs == original.input_artifact_refs
        assert restored.output_artifact_refs == original.output_artifact_refs
        assert restored.prompt == original.prompt
        assert restored.model == original.model
        assert restored.tool_calls == original.tool_calls
        assert restored.latency_ms == original.latency_ms
        assert restored.trace_id == original.trace_id
        assert restored.error == original.error
        assert restored.timestamp == original.timestamp

    def test_json_serialization_roundtrip(self) -> None:
        """model_dump(mode='json') -> JSON string -> model_validate should roundtrip."""
        original = ExecutionRecord(
            id="rec-json-001",
            run_id="run-json-001",
            task_id="step_a",
            agent_id="local://echo",
            status=TaskStatus.FAILED,
            latency_ms=500,
            trace_id="trace-json-001",
            error="Connection refused",
        )

        json_data = original.model_dump(mode="json")
        json_str = json.dumps(json_data)
        parsed = json.loads(json_str)
        restored = ExecutionRecord.model_validate(parsed)

        assert restored.id == original.id
        assert restored.status == TaskStatus.FAILED
        assert restored.error == "Connection refused"
        assert restored.latency_ms == 500

    def test_run_summary_roundtrip(self) -> None:
        """RunSummary model_dump -> model_validate roundtrip."""
        original = RunSummary(
            run_id="run-rs-001",
            workflow_name="test-wf",
            status="completed",
            total_nodes=5,
            completed_nodes=4,
            failed_nodes=1,
            skipped_nodes=0,
            forked_from="run-parent",
            forked_at_step="validator",
        )

        dumped = original.model_dump()
        restored = RunSummary.model_validate(dumped)

        assert restored.run_id == original.run_id
        assert restored.workflow_name == original.workflow_name
        assert restored.total_nodes == original.total_nodes
        assert restored.completed_nodes == original.completed_nodes
        assert restored.failed_nodes == original.failed_nodes
        assert restored.forked_from == original.forked_from
        assert restored.forked_at_step == original.forked_at_step


# ===========================================================================
# CAT-11: TC-MDL-007 — AgentInfo missing required fields
# ===========================================================================


class TestAgentInfoRequiredFields:
    """TC-MDL-007: AgentInfo rejects missing required fields."""

    def test_missing_id_raises(self) -> None:
        """AgentInfo without 'id' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AgentInfo(endpoint="http://x", name="X")  # type: ignore[call-arg]
        assert "id" in str(exc_info.value)

    def test_missing_endpoint_raises(self) -> None:
        """AgentInfo without 'endpoint' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AgentInfo(id="a1", name="X")  # type: ignore[call-arg]
        assert "endpoint" in str(exc_info.value)

    def test_missing_name_raises(self) -> None:
        """AgentInfo without 'name' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            AgentInfo(id="a1", endpoint="http://x")  # type: ignore[call-arg]
        assert "name" in str(exc_info.value)

    def test_all_required_fields_present_valid(self) -> None:
        """AgentInfo with all required fields is valid."""
        agent = AgentInfo(id="a1", endpoint="http://x", name="Agent")
        assert agent.id == "a1"
        assert agent.health == AgentHealth.ALIVE
        assert agent.capabilities == []

    def test_empty_dict_raises(self) -> None:
        """Constructing AgentInfo from empty dict raises ValidationError."""
        with pytest.raises(ValidationError):
            AgentInfo(**{})  # type: ignore[arg-type]
