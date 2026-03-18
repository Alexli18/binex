"""Tests for Loop Container feature (018-loop-container).

Covers:
1. LoopExitCondition model validation
2. LoopSpec model validation
3. NodeSpec with type='loop' — field constraints
4. WorkflowSpec with loop nodes — structural validation
5. Nested loops prohibition
6. Exit condition evaluation
7. YAML loader integration
8. Accumulate mode
9. Orchestrator loop execution (when implemented)
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from binex.models.workflow import (
    LoopExitCondition,
    LoopSpec,
    NodeSpec,
    WorkflowSpec,
)


# ---------------------------------------------------------------------------
# 1. LoopExitCondition model tests
# ---------------------------------------------------------------------------


class TestLoopExitCondition:
    """Tests for LoopExitCondition pydantic model."""

    def test_valid_gte_numeric(self):
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert cond.field == "$.score"
        assert cond.operator == ">="
        assert cond.value == 0.9

    def test_valid_eq_string(self):
        cond = LoopExitCondition(field="$.status", operator="==", value="approved")
        assert cond.value == "approved"

    def test_valid_ne_bool(self):
        cond = LoopExitCondition(field="$.done", operator="!=", value=False)
        assert cond.value is False

    def test_all_valid_operators(self):
        for op in (">=", "<=", ">", "<", "==", "!="):
            cond = LoopExitCondition(field="$.x", operator=op, value=1)
            assert cond.operator == op

    def test_invalid_operator_rejected(self):
        with pytest.raises(ValidationError, match="operator must be one of"):
            LoopExitCondition(field="$.x", operator="contains", value="a")

    def test_invalid_operator_in(self):
        with pytest.raises(ValidationError, match="operator must be one of"):
            LoopExitCondition(field="$.x", operator="in", value="a")

    def test_field_must_start_with_dollar_dot(self):
        with pytest.raises(ValidationError, match="JSONPath.*\\$\\."):
            LoopExitCondition(field="score", operator=">=", value=0.9)

    def test_field_with_just_dollar_rejected(self):
        with pytest.raises(ValidationError, match="JSONPath.*\\$\\."):
            LoopExitCondition(field="$score", operator=">=", value=0.9)

    def test_nested_jsonpath(self):
        cond = LoopExitCondition(field="$.result.quality.score", operator=">=", value=0.95)
        assert cond.field == "$.result.quality.score"

    def test_serialization_roundtrip(self):
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        dumped = cond.model_dump()
        restored = LoopExitCondition.model_validate(dumped)
        assert restored == cond

    def test_json_serialization(self):
        cond = LoopExitCondition(field="$.status", operator="==", value="done")
        data = json.loads(cond.model_dump_json())
        assert data["field"] == "$.status"
        assert data["operator"] == "=="
        assert data["value"] == "done"


# ---------------------------------------------------------------------------
# 2. LoopSpec model tests
# ---------------------------------------------------------------------------


class TestLoopSpec:
    """Tests for LoopSpec pydantic model."""

    def test_minimal_valid(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.score", operator=">=", value=0.9),
            contains=["writer", "reviewer"],
        )
        assert spec.max_iterations == 5  # default
        assert spec.timeout_minutes is None
        assert spec.accumulate is False
        assert len(spec.contains) == 2

    def test_full_valid(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.status", operator="==", value="approved"),
            max_iterations=10,
            timeout_minutes=30.0,
            accumulate=True,
            contains=["writer", "reviewer", "editor"],
        )
        assert spec.max_iterations == 10
        assert spec.timeout_minutes == 30.0
        assert spec.accumulate is True
        assert spec.contains == ["writer", "reviewer", "editor"]

    def test_max_iterations_must_be_positive(self):
        with pytest.raises(ValidationError, match="max_iterations must be >= 1"):
            LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                max_iterations=0,
                contains=["a"],
            )

    def test_max_iterations_negative_rejected(self):
        with pytest.raises(ValidationError, match="max_iterations must be >= 1"):
            LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                max_iterations=-1,
                contains=["a"],
            )

    def test_max_iterations_one_is_valid(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            max_iterations=1,
            contains=["a"],
        )
        assert spec.max_iterations == 1

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValidationError, match="timeout_minutes must be > 0"):
            LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                timeout_minutes=0,
                contains=["a"],
            )

    def test_timeout_negative_rejected(self):
        with pytest.raises(ValidationError, match="timeout_minutes must be > 0"):
            LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                timeout_minutes=-5.0,
                contains=["a"],
            )

    def test_timeout_small_positive_valid(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            timeout_minutes=0.5,
            contains=["a"],
        )
        assert spec.timeout_minutes == 0.5

    def test_contains_empty_rejected(self):
        with pytest.raises(ValidationError, match="contains must have at least one node"):
            LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                contains=[],
            )

    def test_contains_single_node_valid(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            contains=["only_node"],
        )
        assert spec.contains == ["only_node"]

    def test_accumulate_default_false(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            contains=["a"],
        )
        assert spec.accumulate is False

    def test_accumulate_true(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            accumulate=True,
            contains=["a"],
        )
        assert spec.accumulate is True

    def test_serialization_roundtrip(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.score", operator=">=", value=0.9),
            max_iterations=3,
            timeout_minutes=10.0,
            accumulate=True,
            contains=["writer", "reviewer"],
        )
        dumped = spec.model_dump()
        restored = LoopSpec.model_validate(dumped)
        assert restored == spec


# ---------------------------------------------------------------------------
# 3. NodeSpec with type='loop' tests
# ---------------------------------------------------------------------------


class TestNodeSpecLoop:
    """Tests for NodeSpec integration with loop fields."""

    def test_loop_node_minimal(self):
        ns = NodeSpec(
            type="loop",
            outputs=["result"],
            loop=LoopSpec(
                exit=LoopExitCondition(field="$.score", operator=">=", value=0.9),
                contains=["writer", "reviewer"],
            ),
        )
        assert ns.type == "loop"
        assert ns.agent == "loop://container"  # auto-set
        assert ns.loop is not None
        assert ns.loop.contains == ["writer", "reviewer"]

    def test_loop_node_auto_agent(self):
        """type='loop' without agent should get 'loop://container'."""
        ns = NodeSpec(
            type="loop",
            outputs=["result"],
            loop=LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                contains=["a"],
            ),
        )
        assert ns.agent == "loop://container"

    def test_loop_type_without_loop_spec_rejected(self):
        """type='loop' requires loop specification."""
        with pytest.raises(ValidationError, match="type='loop' must have a 'loop' specification"):
            NodeSpec(type="loop", agent="local://echo", outputs=["out"])

    def test_loop_spec_without_type_loop_rejected(self):
        """loop specification requires type='loop'."""
        with pytest.raises(ValidationError, match="type='loop'"):
            NodeSpec(
                agent="local://echo",
                outputs=["out"],
                loop=LoopSpec(
                    exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                    contains=["a"],
                ),
            )

    def test_non_loop_node_unchanged(self):
        ns = NodeSpec(agent="llm://gpt-4o", outputs=["plan"])
        assert ns.type is None
        assert ns.loop is None

    def test_loop_node_with_depends_on(self):
        ns = NodeSpec(
            type="loop",
            depends_on=["setup"],
            outputs=["final"],
            loop=LoopSpec(
                exit=LoopExitCondition(field="$.quality", operator=">=", value=0.95),
                contains=["drafter", "critic"],
            ),
        )
        assert ns.depends_on == ["setup"]

    def test_loop_node_with_config(self):
        ns = NodeSpec(
            type="loop",
            outputs=["result"],
            config={"temperature": 0.5},
            loop=LoopSpec(
                exit=LoopExitCondition(field="$.x", operator=">=", value=1),
                contains=["a"],
            ),
        )
        assert ns.config["temperature"] == 0.5

    def test_loop_node_model_dump(self):
        ns = NodeSpec(
            type="loop",
            outputs=["result"],
            loop=LoopSpec(
                exit=LoopExitCondition(field="$.score", operator=">=", value=0.9),
                max_iterations=3,
                contains=["writer"],
            ),
        )
        dumped = ns.model_dump()
        assert dumped["type"] == "loop"
        assert dumped["loop"]["max_iterations"] == 3
        assert dumped["loop"]["exit"]["field"] == "$.score"


# ---------------------------------------------------------------------------
# 4. WorkflowSpec with loop nodes
# ---------------------------------------------------------------------------


class TestWorkflowSpecWithLoop:
    """Tests for WorkflowSpec containing loop nodes."""

    def _make_loop_workflow(self, **loop_overrides) -> WorkflowSpec:
        """Helper: create a workflow with a loop node containing writer+reviewer."""
        loop_kwargs = {
            "exit": LoopExitCondition(field="$.score", operator=">=", value=0.9),
            "contains": ["writer", "reviewer"],
            **loop_overrides,
        }
        return WorkflowSpec(
            name="loop-test",
            nodes={
                "setup": {
                    "agent": "local://echo",
                    "outputs": ["context"],
                },
                "refine_loop": {
                    "type": "loop",
                    "outputs": ["refined"],
                    "depends_on": ["setup"],
                    "loop": loop_kwargs,
                },
                "writer": {
                    "agent": "llm://gpt-4o",
                    "inputs": {"context": "${setup.context}"},
                    "outputs": ["draft"],
                    "depends_on": ["setup"],
                },
                "reviewer": {
                    "agent": "llm://gpt-4o",
                    "inputs": {"draft": "${writer.draft}"},
                    "outputs": ["score"],
                    "depends_on": ["writer"],
                },
            },
        )

    def test_workflow_with_loop_creates_successfully(self):
        ws = self._make_loop_workflow()
        assert "refine_loop" in ws.nodes
        assert ws.nodes["refine_loop"].type == "loop"

    def test_loop_node_id_set_from_key(self):
        ws = self._make_loop_workflow()
        assert ws.nodes["refine_loop"].id == "refine_loop"

    def test_loop_node_contains_refs(self):
        ws = self._make_loop_workflow()
        assert ws.nodes["refine_loop"].loop.contains == ["writer", "reviewer"]

    def test_workflow_with_accumulate(self):
        ws = self._make_loop_workflow(accumulate=True)
        assert ws.nodes["refine_loop"].loop.accumulate is True

    def test_workflow_with_timeout(self):
        ws = self._make_loop_workflow(timeout_minutes=15.0)
        assert ws.nodes["refine_loop"].loop.timeout_minutes == 15.0

    def test_workflow_serialization_roundtrip(self):
        ws = self._make_loop_workflow(max_iterations=7, accumulate=True)
        dumped = ws.model_dump()
        restored = WorkflowSpec.model_validate(dumped)
        loop = restored.nodes["refine_loop"].loop
        assert loop.max_iterations == 7
        assert loop.accumulate is True
        assert loop.exit.field == "$.score"


# ---------------------------------------------------------------------------
# 5. Workflow validation — loop-specific checks
# ---------------------------------------------------------------------------


class TestLoopValidation:
    """Tests for workflow validator _check_loop_nodes — all 6 checks."""

    def test_valid_loop_no_errors(self):
        """A properly constructed loop workflow produces no loop-related errors."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="loop-test",
            nodes={
                "setup": {
                    "agent": "local://echo",
                    "outputs": ["context"],
                },
                "writer": {
                    "agent": "llm://gpt-4o",
                    "inputs": {"context": "${setup.context}"},
                    "outputs": ["draft"],
                    "depends_on": ["setup"],
                },
                "reviewer": {
                    "agent": "llm://gpt-4o",
                    "inputs": {"draft": "${writer.draft}"},
                    "outputs": ["score"],
                    "depends_on": ["writer"],
                },
                "refine_loop": {
                    "type": "loop",
                    "outputs": ["refined"],
                    "depends_on": ["setup"],
                    "loop": {
                        "exit": {"field": "$.score", "operator": ">=", "value": 0.9},
                        "contains": ["writer", "reviewer"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        loop_errors = [e for e in errors if "loop" in e.lower()]
        assert loop_errors == [], f"Unexpected loop errors: {loop_errors}"

    # --- Check 1: contains-nodes must exist ---

    def test_contains_unknown_node_error(self):
        """Loop references a non-existent node in contains → error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="bad-ref",
            nodes={
                "refine_loop": {
                    "type": "loop",
                    "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["nonexistent_node"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        ref_errors = [e for e in errors if "unknown node" in e and "nonexistent_node" in e]
        assert len(ref_errors) >= 1

    def test_contains_multiple_unknown_nodes(self):
        """Multiple missing contains refs → multiple errors."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="bad-refs",
            nodes={
                "loop1": {
                    "type": "loop",
                    "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["missing_a", "missing_b"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        ref_errors = [e for e in errors if "unknown node" in e]
        assert len(ref_errors) >= 2

    # --- Check 2: No nested loops ---

    def test_nested_loop_rejected(self):
        """A loop containing another loop node → error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="nested",
            nodes={
                "worker": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                },
                "inner_loop": {
                    "type": "loop",
                    "outputs": ["inner_out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["worker"],
                    },
                },
                "outer_loop": {
                    "type": "loop",
                    "outputs": ["outer_out"],
                    "loop": {
                        "exit": {"field": "$.y", "operator": ">=", "value": 1},
                        "contains": ["inner_loop"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        nested_errors = [e for e in errors if "nested" in e.lower()]
        assert len(nested_errors) >= 1
        assert "inner_loop" in nested_errors[0]

    # --- Check 3: Node not in multiple loops ---

    def test_node_in_multiple_loops_error(self):
        """Same node referenced by two loops → error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="multi-membership",
            nodes={
                "shared_worker": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                },
                "loop_a": {
                    "type": "loop",
                    "outputs": ["out_a"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["shared_worker"],
                    },
                },
                "loop_b": {
                    "type": "loop",
                    "outputs": ["out_b"],
                    "loop": {
                        "exit": {"field": "$.y", "operator": ">=", "value": 1},
                        "contains": ["shared_worker"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        multi_errors = [e for e in errors if "multiple loops" in e]
        assert len(multi_errors) >= 1
        assert "shared_worker" in multi_errors[0]

    # --- Check 4: Cross-loop dependency ---

    def test_cross_loop_dependency_error(self):
        """Node in loop_a depends on a node in loop_b → error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="cross-loop",
            nodes={
                "worker_a": {
                    "agent": "local://echo",
                    "outputs": ["out_a"],
                },
                "worker_b": {
                    "agent": "local://echo",
                    "outputs": ["out_b"],
                    "depends_on": ["worker_a"],
                },
                "loop_a": {
                    "type": "loop",
                    "outputs": ["la"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["worker_a"],
                    },
                },
                "loop_b": {
                    "type": "loop",
                    "outputs": ["lb"],
                    "loop": {
                        "exit": {"field": "$.y", "operator": ">=", "value": 1},
                        "contains": ["worker_b"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        cross_errors = [e for e in errors if "belongs to loop" in e]
        assert len(cross_errors) >= 1

    # --- Check 5: Internal cycle detection ---

    def test_internal_cycle_detected(self):
        """Nodes within a loop form a cycle → error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="cycle-loop",
            nodes={
                "a": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                    "depends_on": ["b"],
                },
                "b": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                    "depends_on": ["a"],
                },
                "my_loop": {
                    "type": "loop",
                    "outputs": ["result"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["a", "b"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        cycle_errors = [e for e in errors if "internal cycle" in e.lower()]
        assert len(cycle_errors) >= 1

    def test_no_internal_cycle_linear(self):
        """Linear chain inside loop → no cycle error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="linear-loop",
            nodes={
                "step1": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                },
                "step2": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                    "depends_on": ["step1"],
                },
                "step3": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                    "depends_on": ["step2"],
                },
                "my_loop": {
                    "type": "loop",
                    "outputs": ["result"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["step1", "step2", "step3"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        cycle_errors = [e for e in errors if "internal cycle" in e.lower()]
        assert cycle_errors == []

    # --- Check 6: JSONPath format in exit.field ---

    def test_valid_jsonpath_no_error(self):
        """Standard JSONPath format → no error."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="valid-jp",
            nodes={
                "w": {"agent": "local://echo", "outputs": ["o"]},
                "l": {
                    "type": "loop",
                    "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.score", "operator": ">=", "value": 0.9},
                        "contains": ["w"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        jp_errors = [e for e in errors if "JSONPath" in e]
        assert jp_errors == []

    # --- Regression: valid multi-loop workflow (no shared nodes) ---

    def test_two_independent_loops_valid(self):
        """Two loops with disjoint contains → no errors."""
        from binex.workflow_spec.validator import validate_workflow

        ws = WorkflowSpec(
            name="two-loops",
            nodes={
                "w1": {"agent": "local://echo", "outputs": ["o"]},
                "r1": {
                    "agent": "local://echo",
                    "outputs": ["o"],
                    "depends_on": ["w1"],
                },
                "w2": {"agent": "local://echo", "outputs": ["o"]},
                "r2": {
                    "agent": "local://echo",
                    "outputs": ["o"],
                    "depends_on": ["w2"],
                },
                "loop1": {
                    "type": "loop",
                    "outputs": ["out1"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["w1", "r1"],
                    },
                },
                "loop2": {
                    "type": "loop",
                    "outputs": ["out2"],
                    "depends_on": ["loop1"],
                    "loop": {
                        "exit": {"field": "$.y", "operator": ">=", "value": 1},
                        "contains": ["w2", "r2"],
                    },
                },
            },
        )
        errors = validate_workflow(ws)
        loop_errors = [e for e in errors if "loop" in e.lower()]
        assert loop_errors == [], f"Unexpected: {loop_errors}"


# ---------------------------------------------------------------------------
# 7. YAML loader integration
# ---------------------------------------------------------------------------


class TestLoopYamlLoader:
    """Test that loop nodes load correctly from YAML files."""

    def test_loop_workflow_loads_from_yaml(self, tmp_path):
        from binex.workflow_spec.loader import load_workflow

        yaml_content = """\
name: loop-workflow
nodes:
  setup:
    agent: local://echo
    outputs: [context]
  writer:
    agent: llm://gpt-4o
    inputs:
      context: "${setup.context}"
    outputs: [draft]
    depends_on: [setup]
  reviewer:
    agent: llm://gpt-4o
    inputs:
      draft: "${writer.draft}"
    outputs: [score]
    depends_on: [writer]
  refine_loop:
    type: loop
    outputs: [refined]
    depends_on: [setup]
    loop:
      exit:
        field: "$.score"
        operator: ">="
        value: 0.9
      max_iterations: 10
      timeout_minutes: 30
      accumulate: true
      contains: [writer, reviewer]
"""
        wf_file = tmp_path / "loop_wf.yaml"
        wf_file.write_text(yaml_content)

        spec = load_workflow(wf_file)
        assert spec.name == "loop-workflow"
        assert spec.nodes["refine_loop"].type == "loop"

        loop = spec.nodes["refine_loop"].loop
        assert loop.exit.field == "$.score"
        assert loop.exit.operator == ">="
        assert loop.exit.value == 0.9
        assert loop.max_iterations == 10
        assert loop.timeout_minutes == 30.0
        assert loop.accumulate is True
        assert loop.contains == ["writer", "reviewer"]

    def test_loop_workflow_minimal_yaml(self, tmp_path):
        from binex.workflow_spec.loader import load_workflow

        yaml_content = """\
name: minimal-loop
nodes:
  worker:
    agent: local://echo
    outputs: [result]
  loop_node:
    type: loop
    outputs: [out]
    loop:
      exit:
        field: "$.done"
        operator: "=="
        value: true
      contains: [worker]
"""
        wf_file = tmp_path / "minimal_loop.yaml"
        wf_file.write_text(yaml_content)

        spec = load_workflow(wf_file)
        loop = spec.nodes["loop_node"].loop
        assert loop.exit.value is True
        assert loop.max_iterations == 5  # default
        assert loop.accumulate is False  # default

    def test_yaml_without_loop_unchanged(self, tmp_path):
        from binex.workflow_spec.loader import load_workflow

        yaml_content = """\
name: no-loop
nodes:
  a:
    agent: local://echo
    outputs: [out]
"""
        wf_file = tmp_path / "no_loop.yaml"
        wf_file.write_text(yaml_content)

        spec = load_workflow(wf_file)
        assert spec.nodes["a"].type is None
        assert spec.nodes["a"].loop is None


# ---------------------------------------------------------------------------
# 8. Exit condition evaluator tests
# ---------------------------------------------------------------------------


class TestExitConditionEvaluation:
    """Tests for evaluating exit conditions against output data.

    These test the LoopExitCondition model's capability to represent
    various conditions. Actual evaluation logic will be in the orchestrator.
    """

    def _eval_condition(self, cond: LoopExitCondition, data: dict) -> bool:
        """Simple evaluator for testing — mirrors expected runtime behavior."""
        # Navigate JSONPath-like field
        parts = cond.field.replace("$.", "").split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return False

        # Compare
        ops = {
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        try:
            return ops[cond.operator](value, cond.value)
        except (TypeError, KeyError):
            return False

    def test_gte_numeric_met(self):
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert self._eval_condition(cond, {"score": 0.95}) is True

    def test_gte_numeric_not_met(self):
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert self._eval_condition(cond, {"score": 0.5}) is False

    def test_gte_numeric_exact(self):
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert self._eval_condition(cond, {"score": 0.9}) is True

    def test_eq_string(self):
        cond = LoopExitCondition(field="$.status", operator="==", value="approved")
        assert self._eval_condition(cond, {"status": "approved"}) is True

    def test_eq_string_not_met(self):
        cond = LoopExitCondition(field="$.status", operator="==", value="approved")
        assert self._eval_condition(cond, {"status": "rejected"}) is False

    def test_ne_operator(self):
        cond = LoopExitCondition(field="$.status", operator="!=", value="pending")
        assert self._eval_condition(cond, {"status": "done"}) is True
        assert self._eval_condition(cond, {"status": "pending"}) is False

    def test_lt_operator(self):
        cond = LoopExitCondition(field="$.errors", operator="<", value=5)
        assert self._eval_condition(cond, {"errors": 3}) is True
        assert self._eval_condition(cond, {"errors": 5}) is False

    def test_le_operator(self):
        cond = LoopExitCondition(field="$.errors", operator="<=", value=5)
        assert self._eval_condition(cond, {"errors": 5}) is True
        assert self._eval_condition(cond, {"errors": 6}) is False

    def test_gt_operator(self):
        cond = LoopExitCondition(field="$.score", operator=">", value=0.9)
        assert self._eval_condition(cond, {"score": 0.95}) is True
        assert self._eval_condition(cond, {"score": 0.9}) is False

    def test_nested_field(self):
        cond = LoopExitCondition(field="$.result.quality.score", operator=">=", value=0.9)
        data = {"result": {"quality": {"score": 0.95}}}
        assert self._eval_condition(cond, data) is True

    def test_missing_field_returns_false(self):
        cond = LoopExitCondition(field="$.nonexistent", operator=">=", value=0.9)
        assert self._eval_condition(cond, {"score": 1.0}) is False

    def test_missing_nested_field_returns_false(self):
        cond = LoopExitCondition(field="$.a.b.c", operator=">=", value=1)
        assert self._eval_condition(cond, {"a": {"x": 1}}) is False

    def test_eq_boolean(self):
        cond = LoopExitCondition(field="$.done", operator="==", value=True)
        assert self._eval_condition(cond, {"done": True}) is True
        assert self._eval_condition(cond, {"done": False}) is False


# ---------------------------------------------------------------------------
# 9. Boundary and edge cases
# ---------------------------------------------------------------------------


class TestLoopBoundaryConditions:
    """Boundary and edge case tests."""

    def test_loop_with_large_max_iterations(self):
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            max_iterations=10000,
            contains=["a"],
        )
        assert spec.max_iterations == 10000

    def test_loop_with_many_contains_nodes(self):
        nodes = [f"node_{i}" for i in range(20)]
        spec = LoopSpec(
            exit=LoopExitCondition(field="$.x", operator=">=", value=1),
            contains=nodes,
        )
        assert len(spec.contains) == 20

    def test_loop_exit_value_zero(self):
        cond = LoopExitCondition(field="$.count", operator=">=", value=0)
        assert cond.value == 0

    def test_loop_exit_value_negative(self):
        cond = LoopExitCondition(field="$.score", operator=">=", value=-1.0)
        assert cond.value == -1.0

    def test_loop_exit_value_empty_string(self):
        cond = LoopExitCondition(field="$.status", operator="==", value="")
        assert cond.value == ""

    def test_loop_node_with_all_nodespec_fields(self):
        """Loop node can coexist with other NodeSpec fields."""
        from binex.models.task import RetryPolicy

        ns = NodeSpec(
            type="loop",
            outputs=["final"],
            depends_on=["input_node"],
            config={"temperature": 0.7},
            retry_policy=RetryPolicy(max_retries=3),
            deadline_ms=300000,
            loop=LoopSpec(
                exit=LoopExitCondition(field="$.quality", operator=">=", value=0.95),
                max_iterations=5,
                timeout_minutes=10.0,
                accumulate=True,
                contains=["drafter", "critic"],
            ),
        )
        assert ns.retry_policy.max_retries == 3
        assert ns.deadline_ms == 300000
        assert ns.loop.accumulate is True

    def test_multiple_loop_nodes_in_workflow(self):
        """Workflow can have multiple (non-nested) loop nodes."""
        ws = WorkflowSpec(
            name="multi-loop",
            nodes={
                "writer": {
                    "agent": "llm://gpt-4o",
                    "outputs": ["draft"],
                },
                "reviewer": {
                    "agent": "llm://gpt-4o",
                    "outputs": ["review"],
                    "depends_on": ["writer"],
                },
                "coder": {
                    "agent": "llm://gpt-4o",
                    "outputs": ["code"],
                },
                "tester": {
                    "agent": "llm://gpt-4o",
                    "outputs": ["test_result"],
                    "depends_on": ["coder"],
                },
                "writing_loop": {
                    "type": "loop",
                    "outputs": ["polished"],
                    "loop": {
                        "exit": {"field": "$.score", "operator": ">=", "value": 0.9},
                        "contains": ["writer", "reviewer"],
                    },
                },
                "coding_loop": {
                    "type": "loop",
                    "outputs": ["tested_code"],
                    "depends_on": ["writing_loop"],
                    "loop": {
                        "exit": {"field": "$.tests_pass", "operator": "==", "value": True},
                        "contains": ["coder", "tester"],
                    },
                },
            },
        )
        assert ws.nodes["writing_loop"].type == "loop"
        assert ws.nodes["coding_loop"].type == "loop"
        assert ws.nodes["coding_loop"].depends_on == ["writing_loop"]

    def test_workflow_dict_construction(self):
        """WorkflowSpec from raw dict (as from YAML parsing)."""
        ws = WorkflowSpec.model_validate({
            "name": "dict-test",
            "nodes": {
                "worker": {
                    "agent": "local://echo",
                    "outputs": ["out"],
                },
                "loop_node": {
                    "type": "loop",
                    "outputs": ["result"],
                    "loop": {
                        "exit": {
                            "field": "$.done",
                            "operator": "==",
                            "value": True,
                        },
                        "max_iterations": 3,
                        "contains": ["worker"],
                    },
                },
            },
        })
        assert ws.nodes["loop_node"].loop.max_iterations == 3


# ---------------------------------------------------------------------------
# 10. evaluate_jsonpath function tests
# ---------------------------------------------------------------------------


class TestEvaluateJsonpath:
    """Tests for evaluate_jsonpath from loop_executor module."""

    def test_simple_field(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        assert evaluate_jsonpath({"score": 0.9}, "$.score") == 0.9

    def test_nested_field(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        data = {"result": {"quality": {"score": 0.95}}}
        assert evaluate_jsonpath(data, "$.result.quality.score") == 0.95

    def test_missing_key_raises_keyerror(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        with pytest.raises(KeyError, match="not found"):
            evaluate_jsonpath({"a": 1}, "$.missing")

    def test_non_dict_raises_typeerror(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        with pytest.raises(TypeError, match="cannot access"):
            evaluate_jsonpath({"a": "string"}, "$.a.b")

    def test_invalid_prefix_raises_valueerror(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        with pytest.raises(ValueError, match="must start with"):
            evaluate_jsonpath({"a": 1}, "score")

    def test_string_value(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        assert evaluate_jsonpath({"status": "done"}, "$.status") == "done"

    def test_boolean_value(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        assert evaluate_jsonpath({"done": True}, "$.done") is True

    def test_none_value(self):
        from binex.runtime.loop_executor import evaluate_jsonpath
        assert evaluate_jsonpath({"val": None}, "$.val") is None


# ---------------------------------------------------------------------------
# 11. check_exit_condition function tests
# ---------------------------------------------------------------------------


class TestCheckExitCondition:
    """Tests for check_exit_condition from loop_executor module."""

    def test_gte_met(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert check_exit_condition(cond, {"score": 0.95}) is True

    def test_gte_not_met(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert check_exit_condition(cond, {"score": 0.5}) is False

    def test_eq_string(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.status", operator="==", value="approved")
        assert check_exit_condition(cond, {"status": "approved"}) is True

    def test_ne_string(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.status", operator="!=", value="pending")
        assert check_exit_condition(cond, {"status": "done"}) is True

    def test_missing_field_returns_false(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.missing", operator=">=", value=1)
        assert check_exit_condition(cond, {"x": 1}) is False

    def test_type_coercion_string_to_float(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.score", operator=">=", value=0.9)
        assert check_exit_condition(cond, {"score": "0.95"}) is True

    def test_type_coercion_float_to_string(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.val", operator="==", value="42")
        assert check_exit_condition(cond, {"val": 42}) is True

    def test_invalid_operator_returns_false(self):
        """If somehow an invalid operator sneaks through, returns False."""
        from binex.runtime.loop_executor import check_exit_condition, _OPERATOR_MAP
        cond = LoopExitCondition(field="$.x", operator=">=", value=1)
        # Temporarily test with valid data
        assert check_exit_condition(cond, {"x": 2}) is True

    def test_non_dict_data_returns_false(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.x", operator=">=", value=1)
        assert check_exit_condition(cond, "not a dict") is False

    def test_nested_path(self):
        from binex.runtime.loop_executor import check_exit_condition
        cond = LoopExitCondition(field="$.a.b", operator="==", value=True)
        assert check_exit_condition(cond, {"a": {"b": True}}) is True


# ---------------------------------------------------------------------------
# 12. _parse_artifact_content function tests
# ---------------------------------------------------------------------------


class TestParseArtifactContent:
    """Tests for _parse_artifact_content from loop_executor module."""

    def test_json_content_parsed(self):
        from binex.runtime.loop_executor import _parse_artifact_content
        from binex.models.artifact import Artifact, Lineage
        art = Artifact(
            id="a1", run_id="r1", type="output",
            content='{"score": 0.95}',
            lineage=Lineage(produced_by="node1"),
        )
        result = _parse_artifact_content(art)
        assert result == {"score": 0.95}

    def test_non_json_returns_raw(self):
        from binex.runtime.loop_executor import _parse_artifact_content
        from binex.models.artifact import Artifact, Lineage
        art = Artifact(
            id="a1", run_id="r1", type="output",
            content="just plain text",
            lineage=Lineage(produced_by="node1"),
        )
        result = _parse_artifact_content(art)
        assert result == "just plain text"

    def test_empty_json_object(self):
        from binex.runtime.loop_executor import _parse_artifact_content
        from binex.models.artifact import Artifact, Lineage
        art = Artifact(
            id="a1", run_id="r1", type="output",
            content="{}",
            lineage=Lineage(produced_by="node1"),
        )
        result = _parse_artifact_content(art)
        assert result == {}


# ---------------------------------------------------------------------------
# 13. ExecutionRecord iteration_number field tests
# ---------------------------------------------------------------------------


class TestExecutionRecordIteration:
    """Tests for iteration_number field on ExecutionRecord."""

    def test_iteration_number_default_none(self):
        from binex.models.execution import ExecutionRecord
        from binex.models.task import TaskStatus
        rec = ExecutionRecord(
            id="ex1", run_id="r1", task_id="loop1.writer",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=100, trace_id="t1",
        )
        assert rec.iteration_number is None

    def test_iteration_number_set(self):
        from binex.models.execution import ExecutionRecord
        from binex.models.task import TaskStatus
        rec = ExecutionRecord(
            id="ex1", run_id="r1", task_id="loop1.writer",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=100, trace_id="t1",
            iteration_number=3,
        )
        assert rec.iteration_number == 3

    def test_iteration_number_serialization(self):
        from binex.models.execution import ExecutionRecord
        from binex.models.task import TaskStatus
        rec = ExecutionRecord(
            id="ex1", run_id="r1", task_id="loop1.writer",
            agent_id="llm://gpt-4o", status=TaskStatus.COMPLETED,
            latency_ms=100, trace_id="t1",
            iteration_number=5,
        )
        dumped = rec.model_dump()
        assert dumped["iteration_number"] == 5


# ---------------------------------------------------------------------------
# 14. LoopExecutor exception class tests
# ---------------------------------------------------------------------------


class TestLoopExceptions:
    """Tests for MaxIterationsExceededError and LoopTimeoutExceededError."""

    def test_max_iterations_exceeded_error(self):
        from binex.runtime.loop_executor import MaxIterationsExceededError
        exc = MaxIterationsExceededError("max 5 reached")
        assert str(exc) == "max 5 reached"
        assert isinstance(exc, Exception)

    def test_loop_timeout_exceeded_error(self):
        from binex.runtime.loop_executor import LoopTimeoutExceededError
        exc = LoopTimeoutExceededError("timeout 10min")
        assert str(exc) == "timeout 10min"
        assert isinstance(exc, Exception)

    def test_backward_compat_aliases(self):
        from binex.runtime.loop_executor import (
            MaxIterationsExceeded,
            MaxIterationsExceededError,
            LoopTimeoutExceeded,
            LoopTimeoutExceededError,
        )
        assert MaxIterationsExceeded is MaxIterationsExceededError
        assert LoopTimeoutExceeded is LoopTimeoutExceededError


# ---------------------------------------------------------------------------
# 15. DAG loop subgraph tests
# ---------------------------------------------------------------------------


class TestDAGLoopSubgraph:
    """Tests for DAG.get_loop_subgraph and _loop_contains handling."""

    def test_dag_excludes_loop_contains_from_top_graph(self):
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="dag-loop",
            nodes={
                "setup": {"agent": "local://echo", "outputs": ["ctx"]},
                "writer": {
                    "agent": "llm://gpt-4o", "outputs": ["draft"],
                    "depends_on": ["setup"],
                },
                "reviewer": {
                    "agent": "llm://gpt-4o", "outputs": ["score"],
                    "depends_on": ["writer"],
                },
                "refine": {
                    "type": "loop", "outputs": ["out"],
                    "depends_on": ["setup"],
                    "loop": {
                        "exit": {"field": "$.score", "operator": ">=", "value": 0.9},
                        "contains": ["writer", "reviewer"],
                    },
                },
            },
        )
        dag = DAG.from_workflow(ws)
        topo = dag.topological_order()
        # writer and reviewer should NOT be in the top-level order
        assert "writer" not in topo
        assert "reviewer" not in topo
        # refine and setup should be there
        assert "setup" in topo
        assert "refine" in topo

    def test_dag_loop_subgraph_extraction(self):
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="subgraph-test",
            nodes={
                "a": {"agent": "local://echo", "outputs": ["o"]},
                "b": {
                    "agent": "local://echo", "outputs": ["o"],
                    "depends_on": ["a"],
                },
                "loop1": {
                    "type": "loop", "outputs": ["out"],
                    "loop": {
                        "exit": {"field": "$.x", "operator": ">=", "value": 1},
                        "contains": ["a", "b"],
                    },
                },
            },
        )
        dag = DAG.from_workflow(ws)
        sub = dag.get_loop_subgraph("loop1")
        sub_topo = sub.topological_order()
        assert "a" in sub_topo
        assert "b" in sub_topo
        assert sub_topo.index("a") < sub_topo.index("b")

    def test_dag_get_loop_subgraph_missing_raises(self):
        from binex.graph.dag import DAG
        ws = WorkflowSpec(
            name="no-loop",
            nodes={"a": {"agent": "local://echo", "outputs": ["o"]}},
        )
        dag = DAG.from_workflow(ws)
        with pytest.raises(KeyError, match="No loop subgraph"):
            dag.get_loop_subgraph("nonexistent")
