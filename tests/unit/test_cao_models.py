"""Unit tests for CaoConfig Pydantic model validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from binex.models.workflow import CaoConfig, NodeSpec


class TestCaoConfigDefaults:
    def test_defaults(self):
        cfg = CaoConfig()
        assert cfg.mode == "handoff"
        assert cfg.provider is None
        assert cfg.output_format == "auto"
        assert cfg.output_field is None
        assert cfg.timeout_minutes == 60

    def test_all_fields(self):
        cfg = CaoConfig(
            mode="handoff",
            provider="claude_code",
            output_format="json",
            output_field="$.result",
            timeout_minutes=30,
        )
        assert cfg.provider == "claude_code"
        assert cfg.output_format == "json"
        assert cfg.output_field == "$.result"
        assert cfg.timeout_minutes == 30


class TestCaoConfigValidation:
    def test_output_field_requires_json_format(self):
        with pytest.raises(ValidationError, match="output_field requires output_format='json'"):
            CaoConfig(output_format="text", output_field="$.result")

    def test_output_field_requires_json_format_auto(self):
        with pytest.raises(ValidationError, match="output_field requires output_format='json'"):
            CaoConfig(output_format="auto", output_field="$.result")

    def test_output_field_must_start_with_dollar_dot(self):
        with pytest.raises(ValidationError, match="must be a JSONPath starting with"):
            CaoConfig(output_format="json", output_field="result")

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValidationError, match="timeout_minutes must be >= 1"):
            CaoConfig(timeout_minutes=0)

    def test_timeout_negative(self):
        with pytest.raises(ValidationError, match="timeout_minutes must be >= 1"):
            CaoConfig(timeout_minutes=-5)

    def test_valid_modes(self):
        cfg = CaoConfig(mode="handoff")
        assert cfg.mode == "handoff"

    def test_invalid_mode(self):
        with pytest.raises(ValidationError):
            CaoConfig(mode="invalid")

    def test_invalid_output_format(self):
        with pytest.raises(ValidationError):
            CaoConfig(output_format="xml")

    def test_output_field_with_json_format_valid(self):
        cfg = CaoConfig(output_format="json", output_field="$.data.items")
        assert cfg.output_field == "$.data.items"

    def test_output_field_nested_jsonpath(self):
        cfg = CaoConfig(output_format="json", output_field="$.a.b.c")
        assert cfg.output_field == "$.a.b.c"

    def test_cao_config_max_human_prompts_default(self):
        cfg = CaoConfig()
        assert cfg.max_human_prompts == 10

    def test_cao_config_max_human_prompts_custom(self):
        cfg = CaoConfig(max_human_prompts=5)
        assert cfg.max_human_prompts == 5

    def test_cao_config_max_human_prompts_zero_invalid(self):
        with pytest.raises(ValidationError, match="max_human_prompts must be >= 1"):
            CaoConfig(max_human_prompts=0)


class TestNodeSpecCaoField:
    def test_nodespec_cao_none_by_default(self):
        node = NodeSpec(agent="llm://gpt-4", outputs=["result"])
        assert node.cao is None

    def test_nodespec_cao_embedded(self):
        node = NodeSpec(
            agent="cao://code_supervisor",
            outputs=["result"],
            cao=CaoConfig(provider="claude_code", timeout_minutes=30),
        )
        assert node.cao is not None
        assert node.cao.provider == "claude_code"
        assert node.cao.timeout_minutes == 30

    def test_nodespec_cao_from_dict(self):
        node = NodeSpec(
            agent="cao://test",
            outputs=["out"],
            cao={"output_format": "json", "output_field": "$.result"},
        )
        assert node.cao is not None
        assert node.cao.output_format == "json"
