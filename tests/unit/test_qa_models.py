"""QA P1 model validation tests.

TC-MOD-001: NodeSpec with empty/invalid agent strings
TC-MOD-003: RetryPolicy with max_retries=-1 and max_retries=0
TC-MOD-004: Artifact with invalid status (not "complete"/"partial")
TC-MOD-007: TaskNode with deadline_ms=0 and deadline_ms=-1
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from binex.models.artifact import Artifact, Lineage
from binex.models.task import RetryPolicy, TaskNode, TaskStatus
from binex.models.workflow import NodeSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_lineage() -> Lineage:
    """Return a minimal valid Lineage instance."""
    return Lineage(produced_by="test-node")


def _minimal_artifact(**overrides) -> dict:
    """Return the minimal valid Artifact kwargs, with optional overrides."""
    base = {
        "id": "art-1",
        "run_id": "run-1",
        "type": "text",
        "content": "hello",
        "lineage": _minimal_lineage(),
    }
    base.update(overrides)
    return base


def _minimal_task_node(**overrides) -> dict:
    """Return the minimal valid TaskNode kwargs, with optional overrides."""
    base = {
        "id": "t1",
        "run_id": "r1",
        "node_id": "step1",
        "agent": "local://echo",
    }
    base.update(overrides)
    return base


# ===================================================================
# TC-MOD-001: NodeSpec with empty/invalid agent strings
# ===================================================================


class TestNodeSpecAgentValidation:
    """TC-MOD-001: empty, whitespace-only, and no-protocol-prefix agent strings."""

    def test_empty_agent_string_accepted(self) -> None:
        """Empty string is accepted — no min_length constraint on agent."""
        node = NodeSpec(agent="", outputs=["result"])
        assert node.agent == ""

    def test_whitespace_only_agent_accepted(self) -> None:
        """Whitespace-only string is accepted — no strip/validation constraint."""
        node = NodeSpec(agent="   ", outputs=["result"])
        assert node.agent == "   "

    def test_agent_no_protocol_prefix_accepted(self) -> None:
        """Agent string without local://, llm://, or a2a:// prefix is accepted.

        Protocol validation happens at the CLI/runtime layer, not the model layer.
        """
        node = NodeSpec(agent="just-a-name", outputs=["result"])
        assert node.agent == "just-a-name"

    def test_agent_with_only_protocol_separator(self) -> None:
        """Bare '://' without a scheme name is structurally valid at model level."""
        node = NodeSpec(agent="://", outputs=["result"])
        assert node.agent == "://"

    def test_agent_with_valid_local_prefix(self) -> None:
        """Sanity check: standard local:// prefix works."""
        node = NodeSpec(agent="local://echo", outputs=["out"])
        assert node.agent == "local://echo"

    def test_agent_with_valid_llm_prefix(self) -> None:
        """Sanity check: standard llm:// prefix works."""
        node = NodeSpec(agent="llm://gpt-4o", outputs=["out"])
        assert node.agent == "llm://gpt-4o"

    def test_agent_with_valid_a2a_prefix(self) -> None:
        """Sanity check: standard a2a:// prefix works."""
        node = NodeSpec(agent="a2a://http://localhost:9001", outputs=["out"])
        assert node.agent == "a2a://http://localhost:9001"

    def test_agent_with_unknown_protocol_prefix(self) -> None:
        """Unknown protocol prefix is accepted at model level."""
        node = NodeSpec(agent="grpc://my-service", outputs=["result"])
        assert node.agent == "grpc://my-service"


# ===================================================================
# TC-MOD-003: RetryPolicy with max_retries=-1 and max_retries=0
# ===================================================================


class TestRetryPolicyBoundaryValues:
    """TC-MOD-003: boundary values for max_retries."""

    def test_max_retries_zero_means_no_retry(self) -> None:
        """Zero retries is a valid boundary — means 'do not retry'."""
        policy = RetryPolicy(max_retries=0)
        assert policy.max_retries == 0
        assert policy.backoff == "exponential"

    def test_max_retries_negative_one_accepted(self) -> None:
        """Negative retries accepted — no gt constraint on the field."""
        policy = RetryPolicy(max_retries=-1)
        assert policy.max_retries == -1

    def test_max_retries_one_default(self) -> None:
        """Default value is 1."""
        policy = RetryPolicy()
        assert policy.max_retries == 1

    def test_max_retries_zero_with_fixed_backoff(self) -> None:
        """Zero retries combined with fixed backoff is valid."""
        policy = RetryPolicy(max_retries=0, backoff="fixed")
        assert policy.max_retries == 0
        assert policy.backoff == "fixed"

    def test_max_retries_negative_one_with_exponential_backoff(self) -> None:
        """Negative retries combined with exponential backoff is valid."""
        policy = RetryPolicy(max_retries=-1, backoff="exponential")
        assert policy.max_retries == -1
        assert policy.backoff == "exponential"

    def test_max_retries_zero_embedded_in_node(self) -> None:
        """Zero retries embedded in a NodeSpec is valid."""
        node = NodeSpec(
            agent="llm://gpt-4",
            outputs=["r"],
            retry_policy=RetryPolicy(max_retries=0),
        )
        assert node.retry_policy.max_retries == 0

    def test_max_retries_negative_embedded_in_node(self) -> None:
        """Negative retries embedded in a NodeSpec is valid."""
        node = NodeSpec(
            agent="llm://gpt-4",
            outputs=["r"],
            retry_policy=RetryPolicy(max_retries=-1),
        )
        assert node.retry_policy.max_retries == -1


# ===================================================================
# TC-MOD-004: Artifact with invalid status
# ===================================================================


class TestArtifactStatusValidation:
    """TC-MOD-004: Pydantic Literal validation for Artifact.status."""

    def test_status_complete_accepted(self) -> None:
        """'complete' is a valid status."""
        art = Artifact(**_minimal_artifact(status="complete"))
        assert art.status == "complete"

    def test_status_partial_accepted(self) -> None:
        """'partial' is a valid status."""
        art = Artifact(**_minimal_artifact(status="partial"))
        assert art.status == "partial"

    def test_status_default_is_complete(self) -> None:
        """Default status should be 'complete'."""
        art = Artifact(**_minimal_artifact())
        assert art.status == "complete"

    def test_invalid_status_rejected(self) -> None:
        """Status not in Literal['complete', 'partial'] must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Artifact(**_minimal_artifact(status="invalid"))
        assert "status" in str(exc_info.value)

    def test_status_empty_string_rejected(self) -> None:
        """Empty string is not a valid Literal value."""
        with pytest.raises(ValidationError) as exc_info:
            Artifact(**_minimal_artifact(status=""))
        assert "status" in str(exc_info.value)

    def test_status_failed_rejected(self) -> None:
        """'failed' is not a valid artifact status (it's a TaskStatus, not Artifact status)."""
        with pytest.raises(ValidationError) as exc_info:
            Artifact(**_minimal_artifact(status="failed"))
        assert "status" in str(exc_info.value)

    def test_status_none_rejected(self) -> None:
        """None is not a valid status — the field is not Optional."""
        with pytest.raises(ValidationError):
            Artifact(**_minimal_artifact(status=None))

    def test_status_uppercase_complete_rejected(self) -> None:
        """Case sensitivity: 'COMPLETE' should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Artifact(**_minimal_artifact(status="COMPLETE"))
        assert "status" in str(exc_info.value)

    def test_status_partial_uppercase_rejected(self) -> None:
        """Case sensitivity: 'PARTIAL' should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Artifact(**_minimal_artifact(status="PARTIAL"))
        assert "status" in str(exc_info.value)


# ===================================================================
# TC-MOD-007: TaskNode with deadline_ms=0 and deadline_ms=-1
# ===================================================================


class TestTaskNodeDeadlineBoundary:
    """TC-MOD-007: boundary values for TaskNode.deadline_ms."""

    def test_deadline_ms_zero(self) -> None:
        """Zero deadline is accepted — no gt constraint."""
        tn = TaskNode(**_minimal_task_node(deadline_ms=0))
        assert tn.deadline_ms == 0

    def test_deadline_ms_negative_one(self) -> None:
        """Negative deadline is accepted — no gt constraint."""
        tn = TaskNode(**_minimal_task_node(deadline_ms=-1))
        assert tn.deadline_ms == -1

    def test_deadline_ms_none_default(self) -> None:
        """Default deadline_ms is None."""
        tn = TaskNode(**_minimal_task_node())
        assert tn.deadline_ms is None

    def test_deadline_ms_positive(self) -> None:
        """Standard positive deadline works."""
        tn = TaskNode(**_minimal_task_node(deadline_ms=60000))
        assert tn.deadline_ms == 60000

    def test_deadline_ms_large_value(self) -> None:
        """Large deadline accepted without overflow."""
        tn = TaskNode(**_minimal_task_node(deadline_ms=999_999_999))
        assert tn.deadline_ms == 999_999_999

    def test_deadline_ms_zero_with_retry_policy(self) -> None:
        """Zero deadline combined with a retry policy is valid."""
        tn = TaskNode(
            **_minimal_task_node(
                deadline_ms=0,
                retry_policy=RetryPolicy(max_retries=2),
            )
        )
        assert tn.deadline_ms == 0
        assert tn.retry_policy.max_retries == 2

    def test_deadline_ms_negative_with_running_status(self) -> None:
        """Negative deadline combined with RUNNING status is valid at model level."""
        tn = TaskNode(
            **_minimal_task_node(
                deadline_ms=-1,
                status=TaskStatus.RUNNING,
            )
        )
        assert tn.deadline_ms == -1
        assert tn.status == TaskStatus.RUNNING
