"""Boundary-value and edge-case tests for Binex Pydantic models.

Methodology: equivalence partitioning, boundary value analysis, state-based testing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from binex.models.task import RetryPolicy, TaskStatus
from binex.models.workflow import NodeSpec, WorkflowSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_node(**overrides) -> dict:
    """Return the minimal valid NodeSpec kwargs, with optional overrides."""
    base = {"agent": "llm://gpt-4", "outputs": ["result"]}
    base.update(overrides)
    return base


def _minimal_workflow(**overrides) -> dict:
    """Return the minimal valid WorkflowSpec kwargs, with optional overrides."""
    base = {
        "name": "test-workflow",
        "nodes": {"step1": _minimal_node()},
    }
    base.update(overrides)
    return base


# ===================================================================
# 1. RetryPolicy boundary tests
# ===================================================================


class TestRetryPolicyBoundary:
    """Equivalence partitions: zero retries, negative, large, valid/invalid backoff."""

    def test_max_retries_zero(self):
        """Zero retries is a valid boundary — means 'do not retry'."""
        policy = RetryPolicy(max_retries=0)
        assert policy.max_retries == 0

    def test_max_retries_negative(self):
        """Pydantic accepts negative int (no gt constraint); edge case documented."""
        policy = RetryPolicy(max_retries=-1)
        assert policy.max_retries == -1

    def test_max_retries_large_value(self):
        """Large value should be accepted without overflow."""
        policy = RetryPolicy(max_retries=999_999)
        assert policy.max_retries == 999_999

    def test_default_values(self):
        """Defaults: max_retries=1, backoff='exponential'."""
        policy = RetryPolicy()
        assert policy.max_retries == 1
        assert policy.backoff == "exponential"

    def test_backoff_fixed(self):
        policy = RetryPolicy(backoff="fixed")
        assert policy.backoff == "fixed"

    def test_backoff_exponential(self):
        policy = RetryPolicy(backoff="exponential")
        assert policy.backoff == "exponential"

    def test_backoff_invalid_value_rejected(self):
        """Literal['fixed', 'exponential'] must reject other strings."""
        with pytest.raises(ValidationError) as exc_info:
            RetryPolicy(backoff="linear")
        assert "backoff" in str(exc_info.value)

    def test_backoff_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            RetryPolicy(backoff="")

    def test_max_retries_non_int_rejected(self):
        """Strings that aren't numeric should be rejected."""
        with pytest.raises(ValidationError):
            RetryPolicy(max_retries="abc")


# ===================================================================
# 2. TaskStatus state machine tests
# ===================================================================


class TestTaskStatusStateMachine:
    """State-based testing: verify every valid and invalid transition."""

    def test_all_statuses_present_in_transition_map(self):
        """Every member of TaskStatus must be a key in valid_transitions."""
        transitions = TaskStatus.valid_transitions()
        for status in TaskStatus:
            assert status in transitions, f"{status} missing from valid_transitions"

    def test_valid_transition_requested_to_accepted(self):
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.ACCEPTED in transitions[TaskStatus.REQUESTED]

    def test_valid_transition_accepted_to_running(self):
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.RUNNING in transitions[TaskStatus.ACCEPTED]

    @pytest.mark.parametrize(
        "target",
        [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMED_OUT],
    )
    def test_valid_transitions_from_running(self, target):
        """RUNNING can transition to any of the four terminal/retryable states."""
        transitions = TaskStatus.valid_transitions()
        assert target in transitions[TaskStatus.RUNNING]

    def test_valid_transition_failed_to_requested(self):
        """Retry path: FAILED -> REQUESTED."""
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.REQUESTED in transitions[TaskStatus.FAILED]

    @pytest.mark.parametrize("terminal", [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.TIMED_OUT])
    def test_terminal_states_have_no_transitions(self, terminal):
        transitions = TaskStatus.valid_transitions()
        assert transitions[terminal] == set(), f"{terminal} should be terminal"

    # --- Invalid transitions ---

    def test_invalid_requested_to_completed(self):
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.COMPLETED not in transitions[TaskStatus.REQUESTED]

    def test_invalid_requested_to_running(self):
        """Must go through ACCEPTED first."""
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.RUNNING not in transitions[TaskStatus.REQUESTED]

    def test_invalid_accepted_to_completed(self):
        """Must go through RUNNING first."""
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.COMPLETED not in transitions[TaskStatus.ACCEPTED]

    def test_invalid_completed_to_running(self):
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.RUNNING not in transitions[TaskStatus.COMPLETED]

    def test_invalid_cancelled_to_requested(self):
        """CANCELLED is terminal — no retries."""
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.REQUESTED not in transitions[TaskStatus.CANCELLED]

    def test_invalid_timed_out_to_requested(self):
        """TIMED_OUT is terminal — no retries."""
        transitions = TaskStatus.valid_transitions()
        assert TaskStatus.REQUESTED not in transitions[TaskStatus.TIMED_OUT]

    def test_all_invalid_transitions_exhaustive(self):
        """For every (source, target) pair that is NOT in valid_transitions, confirm it."""
        transitions = TaskStatus.valid_transitions()
        all_statuses = set(TaskStatus)
        for source in TaskStatus:
            invalid_targets = all_statuses - transitions[source] - {source}
            for target in invalid_targets:
                assert target not in transitions[source], (
                    f"Unexpected valid transition {source} -> {target}"
                )

    def test_status_string_values(self):
        """StrEnum values should match their lowercase name."""
        assert TaskStatus.REQUESTED == "requested"
        assert TaskStatus.TIMED_OUT == "timed_out"

    def test_status_count(self):
        """Guard against silent additions/removals."""
        assert len(TaskStatus) == 7


# ===================================================================
# 3. NodeSpec edge cases
# ===================================================================


class TestNodeSpecEdgeCases:

    def test_empty_outputs_list(self):
        """Empty outputs is structurally valid (the workflow may just not produce artifacts)."""
        node = NodeSpec(agent="llm://gpt-4", outputs=[])
        assert node.outputs == []

    def test_empty_agent_string(self):
        """Pydantic allows empty string for agent (no min_length constraint)."""
        node = NodeSpec(agent="", outputs=["x"])
        assert node.agent == ""

    def test_very_long_agent_string(self):
        long_agent = "a2a://agent-" + "x" * 10_000
        node = NodeSpec(agent=long_agent, outputs=["out"])
        assert len(node.agent) > 10_000

    def test_config_with_nested_dicts(self):
        nested = {"llm": {"temperature": 0.7, "params": {"top_p": 0.9, "nested": {"deep": True}}}}
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"], config=nested)
        assert node.config["llm"]["params"]["nested"]["deep"] is True

    def test_deadline_ms_zero(self):
        """Zero deadline — edge boundary."""
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"], deadline_ms=0)
        assert node.deadline_ms == 0

    def test_deadline_ms_negative(self):
        """No gt constraint — pydantic accepts negative."""
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"], deadline_ms=-1)
        assert node.deadline_ms == -1

    def test_deadline_ms_none_default(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"])
        assert node.deadline_ms is None

    def test_unicode_system_prompt_name(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"], system_prompt="recherche-avancée-日本語")
        assert "日本語" in node.system_prompt

    def test_depends_on_self_reference(self):
        """Model layer does not forbid self-dependency; that's a graph-level check."""
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"], depends_on=["myself"])
        node.id = "myself"
        assert node.id in node.depends_on

    def test_retry_policy_embedded(self):
        node = NodeSpec(
            agent="llm://gpt-4",
            outputs=["r"],
            retry_policy=RetryPolicy(max_retries=3, backoff="fixed"),
        )
        assert node.retry_policy.max_retries == 3
        assert node.retry_policy.backoff == "fixed"

    def test_retry_policy_none_default(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"])
        assert node.retry_policy is None

    def test_id_default_empty_string(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"])
        assert node.id == ""

    def test_inputs_default_empty_dict(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["r"])
        assert node.inputs == {}

    def test_missing_required_agent_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            NodeSpec(outputs=["r"])
        assert "agent" in str(exc_info.value)

    def test_missing_required_outputs_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            NodeSpec(agent="llm://gpt-4")
        assert "outputs" in str(exc_info.value)


# ===================================================================
# 4. WorkflowSpec edge cases
# ===================================================================


class TestWorkflowSpecEdgeCases:

    def test_single_node_workflow(self):
        wf = WorkflowSpec(**_minimal_workflow())
        assert len(wf.nodes) == 1

    def test_node_id_auto_assigned_from_key(self):
        """model_validator should set node.id = dict key when id is empty."""
        wf = WorkflowSpec(**_minimal_workflow())
        assert wf.nodes["step1"].id == "step1"

    def test_node_explicit_id_preserved(self):
        """When a node supplies its own id, the validator should NOT overwrite it."""
        nodes = {"step1": {**_minimal_node(), "id": "custom-id"}}
        wf = WorkflowSpec(name="w", nodes=nodes)
        assert wf.nodes["step1"].id == "custom-id"

    def test_empty_description_default(self):
        wf = WorkflowSpec(**_minimal_workflow())
        assert wf.description == ""

    def test_explicit_description(self):
        wf = WorkflowSpec(**_minimal_workflow(description="A test workflow"))
        assert wf.description == "A test workflow"

    def test_name_with_special_characters(self):
        wf = WorkflowSpec(**_minimal_workflow(name="workflow/v2 (beta) — test!"))
        assert wf.name == "workflow/v2 (beta) — test!"

    def test_name_with_unicode(self):
        wf = WorkflowSpec(**_minimal_workflow(name="ワークフロー-测试"))
        assert "测试" in wf.name

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            WorkflowSpec(nodes={"s": _minimal_node()})
        assert "name" in str(exc_info.value)

    def test_missing_nodes_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            WorkflowSpec(name="w")
        assert "nodes" in str(exc_info.value)

    def test_multiple_nodes_all_get_ids(self):
        nodes = {
            "a": _minimal_node(),
            "b": _minimal_node(agent="a2a://other"),
            "c": _minimal_node(agent="local://echo"),
        }
        wf = WorkflowSpec(name="multi", nodes=nodes)
        for key in nodes:
            assert wf.nodes[key].id == key

    def test_defaults_none_by_default(self):
        wf = WorkflowSpec(**_minimal_workflow())
        assert wf.defaults is None

    def test_defaults_provided(self):
        wf = WorkflowSpec(
            **_minimal_workflow(
                defaults={"deadline_ms": 60_000, "retry_policy": {"max_retries": 2}}
            )
        )
        assert wf.defaults.deadline_ms == 60_000
        assert wf.defaults.retry_policy.max_retries == 2

    def test_node_with_depends_on_other_node(self):
        nodes = {
            "fetch": _minimal_node(),
            "process": {**_minimal_node(), "depends_on": ["fetch"]},
        }
        wf = WorkflowSpec(name="dag", nodes=nodes)
        assert wf.nodes["process"].depends_on == ["fetch"]

    def test_empty_name_accepted(self):
        """No min_length on name — empty string is structurally valid."""
        wf = WorkflowSpec(name="", nodes={"s": _minimal_node()})
        assert wf.name == ""
