"""Unit tests for CAO soft validation (warnings) and hard validation (errors)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from binex.models.workflow import CaoConfig, NodeSpec, WorkflowSpec
from binex.workflow_spec.validator import validate_cao_warnings, validate_workflow


def _make_workflow(
    agent: str = "cao://test_profile",
    cao_config: CaoConfig | None = None,
) -> WorkflowSpec:
    """Helper to build a minimal workflow with a CAO node."""
    return WorkflowSpec(
        name="test",
        nodes={
            "n1": NodeSpec(
                agent=agent,
                outputs=["result"],
                cao=cao_config,
            ),
        },
    )


# ---------------------------------------------------------------------------
# Hard validation (errors)
# ---------------------------------------------------------------------------

class TestCaoHardValidation:
    def test_handoff_mode_passes(self):
        spec = _make_workflow(cao_config=CaoConfig(mode="handoff"))
        errors = validate_workflow(spec)
        assert not errors

    def test_invalid_mode_rejected_by_pydantic(self):
        with pytest.raises(Exception):
            CaoConfig(mode="assign")
        with pytest.raises(Exception):
            CaoConfig(mode="send_message")

    def test_no_cao_config_passes(self):
        spec = _make_workflow(cao_config=None)
        errors = validate_workflow(spec)
        assert not errors

    def test_non_cao_node_unaffected(self):
        spec = WorkflowSpec(
            name="test",
            nodes={
                "n1": NodeSpec(agent="llm://gpt-4", outputs=["result"]),
            },
        )
        errors = validate_workflow(spec)
        assert not errors


# ---------------------------------------------------------------------------
# Soft validation (warnings)
# ---------------------------------------------------------------------------

class TestCaoSoftValidation:
    def test_no_cao_nodes_no_warnings(self):
        spec = WorkflowSpec(
            name="test",
            nodes={"n1": NodeSpec(agent="llm://gpt-4", outputs=["out"])},
        )
        warnings = validate_cao_warnings(spec)
        assert warnings == []

    def test_server_down_grey_info(self):
        spec = _make_workflow()
        with patch(
            "binex.workflow_spec.validator._cao_server_reachable", return_value=False,
        ):
            warnings = validate_cao_warnings(
                spec,
                agent_store_dir="/nonexistent/path",
                cao_server_url="http://localhost:9889",
            )
        assert any("server not running" in w for w in warnings)

    def test_profile_missing_yellow_warning(self, tmp_path):
        store_dir = str(tmp_path / "agent-store")
        (tmp_path / "agent-store").mkdir()
        # No profile .md file

        spec = _make_workflow(agent="cao://missing_agent")
        with patch(
            "binex.workflow_spec.validator._cao_server_reachable", return_value=True,
        ):
            warnings = validate_cao_warnings(
                spec,
                agent_store_dir=store_dir,
            )
        assert any("missing_agent" in w and "not found" in w for w in warnings)
        assert any("cao profile install" in w for w in warnings)

    def test_profile_found_no_warning(self, tmp_path):
        store_dir = str(tmp_path / "agent-store")
        (tmp_path / "agent-store").mkdir()
        (tmp_path / "agent-store" / "test_profile.md").write_text("# Agent")

        spec = _make_workflow(agent="cao://test_profile")
        with patch(
            "binex.workflow_spec.validator._cao_server_reachable", return_value=True,
        ):
            warnings = validate_cao_warnings(
                spec,
                agent_store_dir=store_dir,
            )
        # No profile warning (server warning also absent since reachable)
        assert not any("not found" in w for w in warnings)

    def test_server_down_and_profile_missing(self, tmp_path):
        store_dir = str(tmp_path / "agent-store")
        (tmp_path / "agent-store").mkdir()

        spec = _make_workflow(agent="cao://unknown")
        with patch(
            "binex.workflow_spec.validator._cao_server_reachable", return_value=False,
        ):
            warnings = validate_cao_warnings(
                spec,
                agent_store_dir=store_dir,
                cao_server_url="http://localhost:9889",
            )
        # Should have both: server warning + profile warning
        assert any("server not running" in w for w in warnings)
        assert any("unknown" in w and "not found" in w for w in warnings)

    def test_agent_store_dir_missing(self):
        spec = _make_workflow()
        with patch(
            "binex.workflow_spec.validator._cao_server_reachable", return_value=True,
        ):
            warnings = validate_cao_warnings(
                spec,
                agent_store_dir="/totally/fake/path",
            )
        # Profile not found because dir doesn't exist
        assert any("not found" in w for w in warnings)
