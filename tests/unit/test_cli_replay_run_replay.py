"""Tests for cli/replay.py _run_replay async function — covers lines 54-120."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from binex.models.execution import RunSummary
from binex.models.workflow import NodeSpec, WorkflowSpec


def _make_summary(**overrides) -> RunSummary:
    defaults = dict(
        run_id="run_replay",
        workflow_name="test",
        status="completed",
        total_nodes=2,
        completed_nodes=2,
        forked_from="run_orig",
        forked_at_step="step1",
    )
    defaults.update(overrides)
    return RunSummary(**defaults)


def _make_spec(**node_overrides) -> WorkflowSpec:
    """Create a simple WorkflowSpec with configurable nodes."""
    nodes = node_overrides or {
        "step1": NodeSpec(agent="local://echo", outputs=["out"]),
        "step2": NodeSpec(agent="local://echo", outputs=["out"], depends_on=["step1"]),
    }
    return WorkflowSpec(name="test-wf", nodes=nodes)


class TestRunReplayLocalAgents:
    @pytest.mark.asyncio
    async def test_local_agents_registered_and_replay_called(self):
        from binex.cli.replay import _run_replay

        mock_exec = AsyncMock()
        mock_art = MagicMock()
        spec = _make_spec()
        summary = _make_summary()

        with (
            patch("binex.cli.replay.get_stores", return_value=(mock_exec, mock_art)),
            patch("binex.workflow_spec.loader.load_workflow", return_value=spec),
            patch("binex.runtime.replay.ReplayEngine") as MockEngine,
        ):
            engine = MockEngine.return_value
            engine.dispatcher = MagicMock()
            engine.replay = AsyncMock(return_value=summary)

            result = await _run_replay("run_orig", "step1", "fake.yaml", {})

        assert result.run_id == "run_replay"
        engine.replay.assert_awaited_once()
        # Two local:// nodes → register_adapter called twice
        assert engine.dispatcher.register_adapter.call_count == 2
        mock_exec.close.assert_awaited_once()


class TestRunReplayLLMAgent:
    @pytest.mark.asyncio
    async def test_llm_agent_registered_with_config(self):
        from binex.cli.replay import _run_replay

        mock_exec = AsyncMock()
        mock_art = MagicMock()
        spec = _make_spec(**{
            "planner": NodeSpec(
                agent="llm://gpt-4o",
                outputs=["plan"],
                config={"temperature": 0.3, "api_base": "http://proxy:4000", "api_key": "sk-test", "max_tokens": 1024},
            ),
        })
        summary = _make_summary()

        with (
            patch("binex.cli.replay.get_stores", return_value=(mock_exec, mock_art)),
            patch("binex.workflow_spec.loader.load_workflow", return_value=spec),
            patch("binex.runtime.replay.ReplayEngine") as MockEngine,
        ):
            engine = MockEngine.return_value
            engine.dispatcher = MagicMock()
            engine.replay = AsyncMock(return_value=summary)

            await _run_replay("run_orig", "planner", "fake.yaml", {})

        # LLM adapter registered for llm://gpt-4o
        call_args = engine.dispatcher.register_adapter.call_args
        assert call_args[0][0] == "llm://gpt-4o"
        mock_exec.close.assert_awaited_once()


class TestRunReplayA2AAgent:
    @pytest.mark.asyncio
    async def test_a2a_agent_registered(self):
        from binex.cli.replay import _run_replay

        mock_exec = AsyncMock()
        mock_art = MagicMock()
        spec = _make_spec(**{
            "remote": NodeSpec(agent="a2a://http://localhost:9001", outputs=["result"]),
        })
        summary = _make_summary()

        with (
            patch("binex.cli.replay.get_stores", return_value=(mock_exec, mock_art)),
            patch("binex.workflow_spec.loader.load_workflow", return_value=spec),
            patch("binex.runtime.replay.ReplayEngine") as MockEngine,
        ):
            engine = MockEngine.return_value
            engine.dispatcher = MagicMock()
            engine.replay = AsyncMock(return_value=summary)

            await _run_replay("run_orig", "remote", "fake.yaml", {})

        call_args = engine.dispatcher.register_adapter.call_args
        assert call_args[0][0] == "a2a://http://localhost:9001"
        mock_exec.close.assert_awaited_once()


class TestRunReplayAgentSwap:
    @pytest.mark.asyncio
    async def test_agent_swap_overrides_node(self):
        from binex.cli.replay import _run_replay

        mock_exec = AsyncMock()
        mock_art = MagicMock()
        spec = _make_spec(**{
            "step1": NodeSpec(agent="local://echo", outputs=["out"]),
        })
        summary = _make_summary()

        with (
            patch("binex.cli.replay.get_stores", return_value=(mock_exec, mock_art)),
            patch("binex.workflow_spec.loader.load_workflow", return_value=spec),
            patch("binex.runtime.replay.ReplayEngine") as MockEngine,
        ):
            engine = MockEngine.return_value
            engine.dispatcher = MagicMock()
            engine.replay = AsyncMock(return_value=summary)

            # Swap step1 from local:// to llm://
            await _run_replay("run_orig", "step1", "fake.yaml", {"step1": "llm://gpt-4"})

        # Should register llm adapter, not local
        call_args = engine.dispatcher.register_adapter.call_args
        assert call_args[0][0] == "llm://gpt-4"


class TestRunReplayStoreClose:
    @pytest.mark.asyncio
    async def test_store_closed_on_success(self):
        from binex.cli.replay import _run_replay

        mock_exec = AsyncMock()
        mock_art = MagicMock()
        spec = _make_spec()
        summary = _make_summary()

        with (
            patch("binex.cli.replay.get_stores", return_value=(mock_exec, mock_art)),
            patch("binex.workflow_spec.loader.load_workflow", return_value=spec),
            patch("binex.runtime.replay.ReplayEngine") as MockEngine,
        ):
            engine = MockEngine.return_value
            engine.dispatcher = MagicMock()
            engine.replay = AsyncMock(return_value=summary)

            await _run_replay("run_orig", "step1", "fake.yaml", {})

        mock_exec.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_store_closed_on_error(self):
        from binex.cli.replay import _run_replay

        mock_exec = AsyncMock()
        mock_art = MagicMock()
        spec = _make_spec()

        with (
            patch("binex.cli.replay.get_stores", return_value=(mock_exec, mock_art)),
            patch("binex.workflow_spec.loader.load_workflow", return_value=spec),
            patch("binex.runtime.replay.ReplayEngine") as MockEngine,
        ):
            engine = MockEngine.return_value
            engine.dispatcher = MagicMock()
            engine.replay = AsyncMock(side_effect=ValueError("step not found"))

            with pytest.raises(ValueError, match="step not found"):
                await _run_replay("run_orig", "step1", "fake.yaml", {})

        # close() must be called even when replay raises
        mock_exec.close.assert_awaited_once()
