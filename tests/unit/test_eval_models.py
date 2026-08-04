"""Tests for src/binex/eval/models.py (T008)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from binex.eval.models import (
    AssertResult,
    EvalAssert,
    EvalCase,
    EvalCaseResult,
    EvalResult,
    EvalSuite,
    EvalThresholds,
)


# ---------------------------------------------------------------------------
# EvalThresholds
# ---------------------------------------------------------------------------

class TestEvalThresholds:
    def test_defaults_are_none(self):
        t = EvalThresholds()
        assert t.min_similarity is None
        assert t.max_cost_delta is None
        assert t.max_latency_delta_ms is None

    def test_valid_values(self):
        t = EvalThresholds(min_similarity=0.85, max_cost_delta=0.10, max_latency_delta_ms=30000)
        assert t.min_similarity == 0.85
        assert t.max_cost_delta == 0.10
        assert t.max_latency_delta_ms == 30000

    def test_min_similarity_bounds(self):
        with pytest.raises(ValidationError):
            EvalThresholds(min_similarity=-0.1)
        with pytest.raises(ValidationError):
            EvalThresholds(min_similarity=1.1)
        # boundaries valid
        EvalThresholds(min_similarity=0.0)
        EvalThresholds(min_similarity=1.0)

    def test_max_cost_delta_non_negative(self):
        with pytest.raises(ValidationError):
            EvalThresholds(max_cost_delta=-0.01)
        EvalThresholds(max_cost_delta=0.0)

    def test_max_latency_delta_ms_non_negative(self):
        with pytest.raises(ValidationError):
            EvalThresholds(max_latency_delta_ms=-1)
        EvalThresholds(max_latency_delta_ms=0)


# ---------------------------------------------------------------------------
# EvalAssert
# ---------------------------------------------------------------------------

class TestEvalAssert:
    def test_contains_requires_value(self):
        with pytest.raises(ValidationError, match="value"):
            EvalAssert(type="contains")

    def test_not_contains_requires_value(self):
        with pytest.raises(ValidationError, match="value"):
            EvalAssert(type="not_contains")

    def test_regex_requires_pattern(self):
        with pytest.raises(ValidationError, match="pattern"):
            EvalAssert(type="regex")

    def test_json_path_requires_path(self):
        with pytest.raises(ValidationError, match="path"):
            EvalAssert(type="json_path")

    def test_llm_judge_requires_prompt_and_model(self):
        with pytest.raises(ValidationError):
            EvalAssert(type="llm_judge", prompt="check it")  # model missing
        with pytest.raises(ValidationError):
            EvalAssert(type="llm_judge", model="ollama/llama3.2")  # prompt missing

    def test_contains_valid(self):
        a = EvalAssert(type="contains", value="hello", node="researcher")
        assert a.type == "contains"
        assert a.value == "hello"
        assert a.node == "researcher"

    def test_regex_valid(self):
        a = EvalAssert(type="regex", pattern=r"\d{4}")
        assert a.pattern == r"\d{4}"

    def test_json_path_valid(self):
        a = EvalAssert(type="json_path", path="$.questions", exists=True)
        assert a.path == "$.questions"
        assert a.exists is True

    def test_json_path_exists_default_true(self):
        a = EvalAssert(type="json_path", path="$.x")
        assert a.exists is True

    def test_llm_judge_valid(self):
        a = EvalAssert(type="llm_judge", prompt="Is it good?", model="ollama/llama3.2")
        assert a.prompt == "Is it good?"
        assert a.model == "ollama/llama3.2"

    def test_node_defaults_none(self):
        a = EvalAssert(type="contains", value="x")
        assert a.node is None

    def test_unknown_type_rejected(self):
        with pytest.raises(ValidationError):
            EvalAssert(type="unknown_type", value="x")


# ---------------------------------------------------------------------------
# EvalCase
# ---------------------------------------------------------------------------

class TestEvalCase:
    def test_minimal(self):
        c = EvalCase(id="case-1")
        assert c.id == "case-1"
        assert c.inputs == {}
        assert c.thresholds is None
        assert c.asserts == []

    def test_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            EvalCase(id="")

    def test_with_asserts(self):
        c = EvalCase(
            id="q",
            inputs={"input": "hello"},
            asserts=[EvalAssert(type="contains", value="world")],
        )
        assert len(c.asserts) == 1

    def test_case_level_thresholds(self):
        c = EvalCase(id="x", thresholds=EvalThresholds(min_similarity=0.9))
        assert c.thresholds is not None
        assert c.thresholds.min_similarity == 0.9


# ---------------------------------------------------------------------------
# EvalSuite
# ---------------------------------------------------------------------------

class TestEvalSuite:
    def test_minimal_suite(self):
        s = EvalSuite(
            name="my-suite",
            workflow="examples/simple.yaml",
            cases=[EvalCase(id="c1")],
        )
        assert s.name == "my-suite"
        assert len(s.cases) == 1
        assert s.thresholds == EvalThresholds()

    def test_empty_cases_rejected(self):
        with pytest.raises(ValidationError, match="at least one"):
            EvalSuite(name="s", workflow="w.yaml", cases=[])

    def test_duplicate_case_ids_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate case id"):
            EvalSuite(
                name="s",
                workflow="w.yaml",
                cases=[EvalCase(id="dup"), EvalCase(id="dup")],
            )

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            EvalSuite(name="", workflow="w.yaml", cases=[EvalCase(id="c1")])

    def test_empty_workflow_rejected(self):
        with pytest.raises(ValidationError):
            EvalSuite(name="s", workflow="", cases=[EvalCase(id="c1")])


# ---------------------------------------------------------------------------
# AssertResult
# ---------------------------------------------------------------------------

class TestAssertResult:
    def test_valid(self):
        r = AssertResult(assert_index=0, type="contains", status="passed", reason="ok")
        assert r.status == "passed"

    def test_statuses(self):
        for st in ("passed", "failed", "error"):
            AssertResult(assert_index=0, type="x", status=st, reason="r")

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            AssertResult(assert_index=0, type="x", status="unknown", reason="r")


# ---------------------------------------------------------------------------
# EvalCaseResult
# ---------------------------------------------------------------------------

class TestEvalCaseResult:
    def test_minimal(self):
        r = EvalCaseResult(case_id="c1", verdict="no_baseline")
        assert r.run_id is None
        assert r.violated_thresholds == []
        assert r.assert_results == []
        assert r.error is None

    def test_invalid_verdict(self):
        with pytest.raises(ValidationError):
            EvalCaseResult(case_id="c1", verdict="bad_verdict")

    def test_all_verdicts_valid(self):
        for v in ("pass", "fail", "no_baseline"):
            EvalCaseResult(case_id="c1", verdict=v)


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------

class TestEvalResult:
    def test_minimal(self):
        from datetime import UTC, datetime
        r = EvalResult(
            suite_name="s",
            suite_path="/path/s.yaml",
            executed_at=datetime.now(UTC),
            total=3,
            passed=2,
            failed=1,
            no_baseline=0,
            total_cost=0.01,
            cases=[EvalCaseResult(case_id="c1", verdict="pass")],
        )
        assert r.total == 3
        assert r.passed == 2

    def test_model_dump_json_roundtrip(self):
        from datetime import UTC, datetime
        r = EvalResult(
            suite_name="s",
            suite_path="/p",
            executed_at=datetime.now(UTC),
            total=1,
            passed=1,
            failed=0,
            no_baseline=0,
            total_cost=0.0,
            cases=[],
        )
        json_str = r.model_dump_json()
        assert "suite_name" in json_str
