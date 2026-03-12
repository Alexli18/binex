"""Tests: schema_validator, dispatcher schema logic, workflow validator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from binex.models.artifact import Artifact, Lineage
from binex.models.cost import ExecutionResult
from binex.models.task import RetryPolicy, TaskNode
from binex.models.workflow import NodeSpec, WorkflowSpec
from binex.runtime.dispatcher import Dispatcher, SchemaValidationError
from binex.runtime.schema_validator import ValidationResult, validate_output
from binex.workflow_spec.validator import validate_workflow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIMPLE_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string"}},
}

NESTED_SCHEMA = {
    "type": "object",
    "required": ["user"],
    "properties": {
        "user": {
            "type": "object",
            "required": ["first_name", "age"],
            "properties": {
                "first_name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
    },
}


def _make_task(*, output_schema: dict | None = None, max_retries: int = 2) -> TaskNode:
    config: dict = {}
    if output_schema is not None:
        config["output_schema"] = output_schema
    return TaskNode(
        id="task_1",
        node_id="node_a",
        run_id="run_01",
        agent="llm://test",
        inputs={"prompt": "test"},
        config=config,
        retry_policy=RetryPolicy(max_retries=max_retries, backoff="fixed"),
    )


def _make_artifact(content=None) -> Artifact:
    return Artifact(
        id="art_1",
        run_id="run_01",
        type="llm_response",
        content=content,
        lineage=Lineage(produced_by="node_a"),
    )


def _make_execution_result(content=None) -> ExecutionResult:
    return ExecutionResult(artifacts=[_make_artifact(content)])


# ===========================================================================
# TC-SCHM-001 through TC-SCHM-006: schema_validator.py
# ===========================================================================


class TestValidateOutput:
    """Tests for binex.runtime.schema_validator.validate_output."""

    def test_valid_dict_matching_schema(self):
        """TC-SCHM-001: valid dict matching schema -> valid=True."""
        result = validate_output({"name": "Alice"}, SIMPLE_SCHEMA)
        assert result.valid is True
        assert result.errors == []

    def test_valid_json_string(self):
        """TC-SCHM-002: valid JSON string -> valid=True."""
        result = validate_output('{"name": "Bob"}', SIMPLE_SCHEMA)
        assert result.valid is True
        assert result.errors == []

    def test_dict_missing_required_field(self):
        """TC-SCHM-003: dict missing required field -> valid=False with errors."""
        result = validate_output({"age": 30}, SIMPLE_SCHEMA)
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("name" in e for e in result.errors)

    def test_none_output(self):
        """TC-SCHM-004: None -> valid=False, errors=['Output is None']."""
        result = validate_output(None, SIMPLE_SCHEMA)
        assert result.valid is False
        assert result.errors == ["Output is None"]

    def test_non_json_string(self):
        """TC-SCHM-005: non-JSON string -> valid=False."""
        result = validate_output("not json at all", SIMPLE_SCHEMA)
        assert result.valid is False
        assert len(result.errors) == 1
        assert "not valid JSON" in result.errors[0]

    def test_nested_schema_valid(self):
        """TC-SCHM-006: nested schema with nested required properties."""
        valid_data = {"user": {"first_name": "Alice", "age": 25}}
        result = validate_output(valid_data, NESTED_SCHEMA)
        assert result.valid is True
        assert result.errors == []

    def test_nested_schema_missing_nested_required(self):
        """TC-SCHM-006 variant: nested required property missing."""
        invalid_data = {"user": {"first_name": "Alice"}}  # missing 'age'
        result = validate_output(invalid_data, NESTED_SCHEMA)
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("age" in e for e in result.errors)

    def test_nested_schema_wrong_type(self):
        """TC-SCHM-006 variant: nested property has wrong type."""
        invalid_data = {"user": {"first_name": "Alice", "age": "not_an_int"}}
        result = validate_output(invalid_data, NESTED_SCHEMA)
        assert result.valid is False

    def test_nested_schema_json_string(self):
        """TC-SCHM-006 variant: nested schema validated from JSON string."""
        data = json.dumps({"user": {"first_name": "Bob", "age": 42}})
        result = validate_output(data, NESTED_SCHEMA)
        assert result.valid is True

    def test_validation_result_dataclass(self):
        """ValidationResult defaults are correct."""
        r = ValidationResult(valid=True)
        assert r.errors == []
        r2 = ValidationResult(valid=False, errors=["e1", "e2"])
        assert len(r2.errors) == 2


# ===========================================================================
# TC-SCHM-007 through TC-SCHM-011: dispatcher.py schema validation
# ===========================================================================


@pytest.mark.asyncio
class TestDispatcherSchemaValidation:
    """Tests for schema validation logic inside Dispatcher.dispatch."""

    async def test_dispatch_with_valid_schema_returns_result(self):
        """TC-SCHM-007: output_schema that passes validation returns result."""
        mock_adapter = AsyncMock()
        mock_adapter.execute.return_value = _make_execution_result({"name": "test"})

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=SIMPLE_SCHEMA)
        result = await dispatcher.dispatch(task, [], "trace_01")

        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == {"name": "test"}
        mock_adapter.execute.assert_called_once()

    @patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_dispatch_retries_on_schema_failure(self, mock_sleep):
        """TC-SCHM-008: retries on validation failure (bad then good)."""
        mock_adapter = AsyncMock()
        bad_result = _make_execution_result({"wrong": "field"})
        good_result = _make_execution_result({"name": "fixed"})
        mock_adapter.execute.side_effect = [bad_result, good_result]

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=SIMPLE_SCHEMA, max_retries=2)
        result = await dispatcher.dispatch(task, [], "trace_01")

        assert result.artifacts[0].content == {"name": "fixed"}
        assert mock_adapter.execute.call_count == 2
        mock_sleep.assert_called_once()

    @patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_dispatch_raises_after_max_retries(self, mock_sleep):
        """TC-SCHM-009: raises SchemaValidationError after max retries exhausted."""
        mock_adapter = AsyncMock()
        mock_adapter.execute.return_value = _make_execution_result({"bad": "data"})

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=SIMPLE_SCHEMA, max_retries=2)

        with pytest.raises(SchemaValidationError, match="validation failed after 2 attempts"):
            await dispatcher.dispatch(task, [], "trace_01")

        assert mock_adapter.execute.call_count == 2

    @patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_dispatch_adds_feedback_artifact_on_retry(self, mock_sleep):
        """TC-SCHM-010: adds feedback artifact when retrying schema validation."""
        mock_adapter = AsyncMock()
        bad_result = _make_execution_result({"wrong": "field"})
        good_result = _make_execution_result({"name": "ok"})
        mock_adapter.execute.side_effect = [bad_result, good_result]

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=SIMPLE_SCHEMA, max_retries=2)
        result = await dispatcher.dispatch(task, [], "trace_01")

        # The second call should have received the feedback artifact
        second_call_args = mock_adapter.execute.call_args_list[1]
        input_artifacts = second_call_args[0][1]  # positional arg: input_artifacts
        feedback_artifacts = [a for a in input_artifacts if a.type == "feedback"]
        assert len(feedback_artifacts) == 1
        assert "Schema validation failed" in feedback_artifacts[0].content
        assert feedback_artifacts[0].lineage.produced_by == "schema_validator"

        # Final result is the good one
        assert result.artifacts[0].content == {"name": "ok"}

    async def test_dispatch_without_schema_skips_validation(self):
        """TC-SCHM-011: no output_schema -> validation skipped entirely."""
        mock_adapter = AsyncMock()
        # Content doesn't match any schema — that's fine since there's no schema
        mock_adapter.execute.return_value = _make_execution_result("arbitrary string content")

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=None)
        result = await dispatcher.dispatch(task, [], "trace_01")

        assert len(result.artifacts) == 1
        assert result.artifacts[0].content == "arbitrary string content"
        mock_adapter.execute.assert_called_once()

    async def test_dispatch_empty_config_skips_validation(self):
        """Variant: empty config dict -> no output_schema -> skips validation."""
        mock_adapter = AsyncMock()
        mock_adapter.execute.return_value = _make_execution_result(42)

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = TaskNode(
            id="t1",
            node_id="n1",
            run_id="r1",
            agent="llm://test",
            inputs={},
            config={},
        )
        result = await dispatcher.dispatch(task, [], "trace_01")
        assert result.artifacts[0].content == 42

    @patch("binex.runtime.dispatcher.asyncio.sleep", new_callable=AsyncMock)
    async def test_dispatch_schema_error_not_swallowed_by_generic_retry(self, mock_sleep):
        """SchemaValidationError is re-raised, not caught by generic except."""
        mock_adapter = AsyncMock()
        mock_adapter.execute.return_value = _make_execution_result({"no_name": True})

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=SIMPLE_SCHEMA, max_retries=1)

        with pytest.raises(SchemaValidationError):
            await dispatcher.dispatch(task, [], "trace_01")

    async def test_dispatch_legacy_list_return_with_schema(self):
        """Legacy adapter returning list[Artifact] still gets schema-validated."""
        mock_adapter = AsyncMock()
        # Return list[Artifact] instead of ExecutionResult
        mock_adapter.execute.return_value = [_make_artifact({"name": "legacy"})]

        dispatcher = Dispatcher()
        dispatcher.register_adapter("llm://test", mock_adapter)

        task = _make_task(output_schema=SIMPLE_SCHEMA)
        result = await dispatcher.dispatch(task, [], "trace_01")
        assert result.artifacts[0].content == {"name": "legacy"}


# ===========================================================================
# TC-SCHM-012 through TC-SCHM-015: workflow_spec/validator.py
# ===========================================================================


def _make_workflow(output_schema=None) -> WorkflowSpec:
    node_kwargs: dict = {
        "id": "node_a",
        "agent": "llm://test",
        "inputs": {"prompt": "test"},
        "outputs": ["output"],
    }
    if output_schema is not None:
        node_kwargs["output_schema"] = output_schema
    return WorkflowSpec(
        name="test",
        nodes={"node_a": NodeSpec(**node_kwargs)},
    )


class TestWorkflowValidatorOutputSchema:
    """Tests for output_schema validation in workflow_spec/validator.py."""

    def test_valid_output_schema_accepted(self):
        """TC-SCHM-012: valid output_schema on a node -> no errors."""
        spec = _make_workflow(output_schema={
            "type": "object",
            "properties": {"name": {"type": "string"}},
        })
        errors = validate_workflow(spec)
        assert errors == []

    def test_non_dict_output_schema_rejected(self):
        """TC-SCHM-013: non-dict output_schema (e.g. string) -> error."""
        # NodeSpec has output_schema typed as dict|None, but pydantic may coerce.
        # We need to bypass pydantic validation to test the workflow validator.
        spec = _make_workflow(output_schema={
            "type": "object",
            "properties": {"x": {"type": "string"}},
        })
        # Manually override with a non-dict value to test validator logic
        spec.nodes["node_a"].output_schema = "not_a_dict"  # type: ignore[assignment]
        errors = validate_workflow(spec)
        schema_errors = [e for e in errors if "output_schema" in e]
        assert len(schema_errors) == 1
        assert "must be a JSON Schema object" in schema_errors[0]

    def test_invalid_json_schema_rejected(self):
        """TC-SCHM-014: invalid JSON Schema (e.g. unknown type) -> error."""
        spec = _make_workflow(output_schema={"type": "invalid_type_xyz"})
        errors = validate_workflow(spec)
        schema_errors = [e for e in errors if "output_schema" in e or "JSON Schema" in e]
        assert len(schema_errors) >= 1
        assert any(
            "invalid" in e.lower() for e in schema_errors
        )

    def test_none_output_schema_accepted(self):
        """TC-SCHM-015: None output_schema -> no errors."""
        spec = _make_workflow(output_schema=None)
        errors = validate_workflow(spec)
        assert errors == []

    def test_complex_valid_schema_accepted(self):
        """Valid complex schema with nested properties passes."""
        spec = _make_workflow(output_schema=NESTED_SCHEMA)
        errors = validate_workflow(spec)
        assert errors == []

    def test_schema_with_additional_properties_false(self):
        """Valid schema with additionalProperties constraint passes."""
        spec = _make_workflow(output_schema={
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "additionalProperties": False,
        })
        errors = validate_workflow(spec)
        assert errors == []

    def test_multiple_nodes_mixed_schemas(self):
        """Workflow with multiple nodes, some with schemas, some without."""
        spec = WorkflowSpec(
            name="multi",
            nodes={
                "a": NodeSpec(
                    id="a",
                    agent="llm://test",
                    inputs={"p": "test"},
                    outputs=["out"],
                    output_schema={"type": "object", "properties": {"v": {"type": "string"}}},
                ),
                "b": NodeSpec(
                    id="b",
                    agent="llm://test",
                    inputs={"p": "${a.out}"},
                    outputs=["out"],
                    depends_on=["a"],
                    output_schema=None,
                ),
            },
        )
        errors = validate_workflow(spec)
        assert errors == []

    def test_multiple_nodes_one_invalid_schema(self):
        """Only the node with invalid schema produces an error."""
        spec = WorkflowSpec(
            name="multi",
            nodes={
                "good": NodeSpec(
                    id="good",
                    agent="llm://test",
                    inputs={"p": "test"},
                    outputs=["out"],
                    output_schema={"type": "object"},
                ),
                "bad": NodeSpec(
                    id="bad",
                    agent="llm://test",
                    inputs={"p": "${good.out}"},
                    outputs=["out"],
                    depends_on=["good"],
                ),
            },
        )
        # Manually set invalid schema to bypass pydantic
        spec.nodes["bad"].output_schema = 12345  # type: ignore[assignment]
        errors = validate_workflow(spec)
        schema_errors = [e for e in errors if "output_schema" in e]
        assert len(schema_errors) == 1
        assert "bad" in schema_errors[0]
