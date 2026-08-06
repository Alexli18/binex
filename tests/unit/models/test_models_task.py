"""Tests for TaskNode, TaskStatus, and RetryPolicy models."""

from binex.models.task import RetryPolicy, TaskNode, TaskStatus


class TestTaskStatus:
    def test_values(self) -> None:
        assert TaskStatus.REQUESTED == "requested"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.TIMED_OUT == "timed_out"

    def test_valid_transitions(self) -> None:
        t = TaskStatus.valid_transitions()
        assert TaskStatus.ACCEPTED in t[TaskStatus.REQUESTED]
        assert TaskStatus.RUNNING in t[TaskStatus.ACCEPTED]
        assert TaskStatus.COMPLETED in t[TaskStatus.RUNNING]
        assert TaskStatus.FAILED in t[TaskStatus.RUNNING]
        assert TaskStatus.CANCELLED in t[TaskStatus.RUNNING]
        assert TaskStatus.TIMED_OUT in t[TaskStatus.RUNNING]
        assert TaskStatus.REQUESTED in t[TaskStatus.FAILED]  # retry
        assert len(t[TaskStatus.COMPLETED]) == 0

    def test_terminal_states_have_no_transitions(self) -> None:
        t = TaskStatus.valid_transitions()
        assert len(t[TaskStatus.COMPLETED]) == 0
        assert len(t[TaskStatus.CANCELLED]) == 0
        assert len(t[TaskStatus.TIMED_OUT]) == 0


class TestRetryPolicy:
    def test_defaults(self) -> None:
        rp = RetryPolicy()
        assert rp.max_retries == 1
        assert rp.backoff == "exponential"

    def test_custom(self) -> None:
        rp = RetryPolicy(max_retries=3, backoff="fixed")
        assert rp.max_retries == 3
        assert rp.backoff == "fixed"


class TestTaskNode:
    def test_create_minimal(self) -> None:
        tn = TaskNode(id="t1", run_id="r1", node_id="planner", agent="local://echo")
        assert tn.status == TaskStatus.REQUESTED
        assert tn.attempt == 1
        assert tn.input_artifact_refs == []
        assert tn.output_artifact_refs == []
        assert tn.system_prompt is None
        assert tn.retry_policy is None
        assert tn.deadline_ms is None

    def test_create_full(self) -> None:
        tn = TaskNode(
            id="t2",
            run_id="r1",
            node_id="validator",
            agent="http://localhost:9004",
            system_prompt="analysis.validate",
            status=TaskStatus.RUNNING,
            input_artifact_refs=["art_01"],
            output_artifact_refs=["art_02"],
            attempt=2,
            retry_policy=RetryPolicy(max_retries=3),
            deadline_ms=60000,
        )
        assert tn.status == TaskStatus.RUNNING
        assert tn.attempt == 2
        assert tn.deadline_ms == 60000
