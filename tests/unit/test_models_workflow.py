"""Tests for WorkflowSpec, NodeSpec, and DefaultsSpec models."""

from binex.models.task import RetryPolicy
from binex.models.workflow import DefaultsSpec, NodeSpec, WorkflowSpec


class TestNodeSpec:
    def test_create_minimal(self) -> None:
        ns = NodeSpec(agent="local://echo", outputs=["result"])
        assert ns.id == ""
        assert ns.skill is None
        assert ns.inputs == {}
        assert ns.depends_on == []
        assert ns.retry_policy is None
        assert ns.deadline_ms is None

    def test_create_full(self) -> None:
        ns = NodeSpec(
            id="planner",
            agent="http://localhost:9001",
            skill="planning.research",
            inputs={"query": "${user.query}"},
            outputs=["execution_plan"],
            depends_on=["setup"],
            retry_policy=RetryPolicy(max_retries=2),
            deadline_ms=60000,
        )
        assert ns.id == "planner"
        assert ns.skill == "planning.research"


class TestDefaultsSpec:
    def test_defaults(self) -> None:
        ds = DefaultsSpec()
        assert ds.deadline_ms == 120000
        assert ds.retry_policy.max_retries == 1
        assert ds.retry_policy.backoff == "exponential"


class TestWorkflowSpec:
    def test_create(self, sample_workflow_dict: dict) -> None:
        ws = WorkflowSpec(**sample_workflow_dict)
        assert ws.name == "test-workflow"
        assert len(ws.nodes) == 2
        assert "producer" in ws.nodes
        assert "consumer" in ws.nodes

    def test_node_ids_set_from_keys(self, sample_workflow_dict: dict) -> None:
        ws = WorkflowSpec(**sample_workflow_dict)
        assert ws.nodes["producer"].id == "producer"
        assert ws.nodes["consumer"].id == "consumer"

    def test_defaults_applied(self, sample_workflow_dict: dict) -> None:
        ws = WorkflowSpec(**sample_workflow_dict)
        assert ws.defaults is not None
        assert ws.defaults.deadline_ms == 30000

    def test_no_defaults(self) -> None:
        ws = WorkflowSpec(
            name="bare",
            nodes={"n1": NodeSpec(agent="local://x", outputs=["out"])},
        )
        assert ws.defaults is None

    def test_research_pipeline(self, sample_research_workflow_dict: dict) -> None:
        ws = WorkflowSpec(**sample_research_workflow_dict)
        assert len(ws.nodes) == 5
        assert ws.nodes["validator"].depends_on == ["researcher_1", "researcher_2"]
        assert ws.nodes["summarizer"].deadline_ms == 60000
