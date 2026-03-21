"""Unit tests for CAOAdapter — mock httpx, full handoff lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.adapters.cao import (
    CAOAdapter,
    CAOAgentError,
    CAOOutputParseError,
    CAOProfileNotFoundError,
    CAOServerUnavailableError,
    CAOTimeoutError,
)
from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import CaoConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_agent_store(tmp_path):
    """Create a temp agent-store with a test profile."""
    store = tmp_path / "agent-store"
    store.mkdir()
    (store / "test_profile.md").write_text("# Test Agent Profile\nA test agent.")
    return str(store)


@pytest.fixture()
def make_adapter(tmp_agent_store):
    """Factory for CAOAdapter with defaults."""
    def _make(
        profile="test_profile",
        server_url="http://localhost:9889",
        cao_config=None,
        session_store=None,
    ):
        return CAOAdapter(
            profile=profile,
            server_url=server_url,
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
            cao_config=cao_config or CaoConfig(),
        )
    return _make


@pytest.fixture()
def task():
    """Minimal TaskNode for testing."""
    return TaskNode(
        id="task_1",
        run_id="run_abc",
        node_id="review",
        agent="cao://test_profile",
        system_prompt="Review the code changes",
    )


@pytest.fixture()
def input_artifacts():
    """Sample input artifacts."""
    return [
        Artifact(
            id="art_prev",
            run_id="run_abc",
            type="result",
            content="Code diff here",
            lineage=Lineage(produced_by="prev_node"),
        )
    ]


def _mock_response(status_code=200, json_data=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealth:
    async def test_health_alive(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))
            mock_client.return_value = client

            result = await adapter.health()
            assert result == AgentHealth.ALIVE

    async def test_health_down(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.return_value = client

            result = await adapter.health()
            assert result == AgentHealth.DOWN

    async def test_health_degraded(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(503))
            mock_client.return_value = client

            result = await adapter.health()
            assert result == AgentHealth.DEGRADED


# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

class TestPreFlightChecks:
    async def test_check_health_ok(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))
            mock_client.return_value = client

            await adapter._check_health()  # should not raise

    async def test_check_health_unavailable(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.return_value = client

            with pytest.raises(CAOServerUnavailableError, match="unavailable"):
                await adapter._check_health()

    def test_check_profile_ok(self, make_adapter):
        adapter = make_adapter(profile="test_profile")
        adapter._check_profile()  # should not raise

    def test_check_profile_not_found(self, make_adapter):
        adapter = make_adapter(profile="nonexistent")
        with pytest.raises(CAOProfileNotFoundError, match="nonexistent"):
            adapter._check_profile()


# ---------------------------------------------------------------------------
# Get or create session
# ---------------------------------------------------------------------------

class TestGetOrCreateSession:
    async def test_create_session_success(self, make_adapter):
        adapter = make_adapter()
        CAOAdapter._run_sessions.clear()
        CAOAdapter._run_session_locks.clear()
        mock_store = AsyncMock()
        adapter.session_store = mock_store

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=
                _mock_response(201, {"id": "term_abc"}),
            )
            mock_client.return_value = client

            session = await adapter._get_or_create_session("run_1", "node_a")

            assert session.terminal_id == "term_abc"
            assert session.session_name == "binex-run_1"
            assert session.run_id == "run_1"
            assert session.status == "active"
            assert "run_1" in CAOAdapter._run_sessions
            mock_store.create_cao_session.assert_awaited_once_with(
                terminal_id="term_abc", run_id="run_1", node_name="node_a",
                session_name="binex-run_1",
            )


# ---------------------------------------------------------------------------
# Wait for init
# ---------------------------------------------------------------------------

class TestWaitForInit:
    async def test_wait_init_immediate(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(200, {"status": "idle"}))
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                await adapter._wait_for_init("term_1")

    async def test_wait_init_error_status(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(200, {"status": "error"}))
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(CAOAgentError, match="error state"):
                    await adapter._wait_for_init("term_1")

    async def test_wait_init_timeout(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(200, {"status": "processing"}))
            mock_client.return_value = client

            with patch("binex.adapters.cao._INIT_TIMEOUT_S", 2):
                with patch("binex.adapters.cao._INIT_POLL_INTERVAL_S", 1.0):
                    with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                        with pytest.raises(CAOTimeoutError, match="did not initialize"):
                            await adapter._wait_for_init("term_1")


# ---------------------------------------------------------------------------
# Send task
# ---------------------------------------------------------------------------

class TestSendTask:
    async def test_send_task_with_artifacts(self, make_adapter, task, input_artifacts):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=_mock_response(200, {"success": True}))
            mock_client.return_value = client

            await adapter._send_task("term_1", task, input_artifacts)

            client.post.assert_awaited_once()
            call_kwargs = client.post.call_args
            sent_params = call_kwargs.kwargs.get("params", {})
            assert "message" in sent_params

    async def test_send_task_empty_inputs(self, make_adapter):
        t = TaskNode(
            id="t1", run_id="r1", node_id="n1",
            agent="cao://test_profile",
        )
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=_mock_response(200, {"success": True}))
            mock_client.return_value = client

            await adapter._send_task("term_1", t, [])
            client.post.assert_awaited_once()


# ---------------------------------------------------------------------------
# Poll until done
# ---------------------------------------------------------------------------

class TestPollUntilDone:
    async def test_poll_completes(self, make_adapter):
        adapter = make_adapter()
        adapter.cao_config.min_wait_seconds = 1
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[
                # poll 1: processing
                _mock_response(200, {"status": "processing"}),
                # poll 2: processing
                _mock_response(200, {"status": "processing"}),
                # poll 3: completed
                _mock_response(200, {"status": "completed"}),
                # output probe (distinguishes pre/post idle)
                _mock_response(200, {"output": "done"}),
            ])
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                await adapter._poll_until_done("term_1", timeout_s=600)

    async def test_poll_error_status(self, make_adapter):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(
                return_value=_mock_response(200, {"status": "error"}),
            )
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(CAOAgentError, match="error state"):
                    await adapter._poll_until_done("term_1", timeout_s=600)

    async def test_poll_timeout(self, make_adapter):
        adapter = make_adapter(cao_config=CaoConfig(timeout_minutes=1))
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(
                return_value=_mock_response(200, {"status": "processing"}),
            )
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(CAOTimeoutError, match="timed out"):
                    await adapter._poll_until_done("term_1", timeout_s=4)

    async def test_poll_waiting_user_answer_with_human_input(self, make_adapter):
        """waiting_user_answer gets human input, sends it, and resumes polling."""
        adapter = make_adapter()
        adapter._human_input_fn = lambda p, t: "yes"
        adapter._human_prompt_count = 0
        adapter.cao_config.min_wait_seconds = 1  # disable min_wait for test

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[
                # poll 1: waiting_user_answer
                _mock_response(200, {"status": "waiting_user_answer"}),
                # poll 2: processing (after human input sent)
                _mock_response(200, {"status": "processing"}),
                # poll 3: idle (done)
                _mock_response(200, {"status": "idle"}),
            ])
            client.post = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                await adapter._poll_until_done("term_1", timeout_s=600)

            # Verify input was sent to terminal
            post_calls = client.post.call_args_list
            assert len(post_calls) == 1
            assert post_calls[0][0][0] == "/terminals/term_1/input"
            assert post_calls[0][1]["params"]["message"] == "yes"

    async def test_waiting_user_answer_emits_event(self, make_adapter):
        """waiting_user_answer should emit cao:waiting_input event."""
        events = []
        async def capture(e):
            events.append(e)

        adapter = make_adapter()
        adapter._event_callback = capture
        adapter._human_input_fn = lambda p, t: "yes"
        adapter._human_prompt_count = 0
        adapter.cao_config.min_wait_seconds = 1

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[
                _mock_response(200, {"status": "waiting_user_answer"}),
                _mock_response(200, {"status": "processing"}),
                _mock_response(200, {"status": "idle"}),
            ])
            client.post = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                await adapter._poll_until_done("term_1", timeout_s=600)

        waiting_events = [e for e in events if e["type"] == "cao:waiting_input"]
        assert len(waiting_events) == 1
        assert waiting_events[0]["terminal_id"] == "term_1"
        assert waiting_events[0]["prompt_number"] == 1

    async def test_waiting_user_answer_max_prompts_exceeded(self, make_adapter):
        """Exceeding max_human_prompts raises CAOAgentError."""
        adapter = make_adapter(cao_config=CaoConfig(max_human_prompts=1))
        adapter._human_input_fn = lambda p, t: "yes"
        adapter._human_prompt_count = 0

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=[
                # First waiting_user_answer — allowed (count becomes 1)
                _mock_response(200, {"status": "waiting_user_answer"}),
                # After input sent, still waiting — second prompt
                _mock_response(200, {"status": "waiting_user_answer"}),
            ])
            client.post = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(CAOAgentError, match="max_human_prompts"):
                    await adapter._poll_until_done("term_1", timeout_s=600)


# ---------------------------------------------------------------------------
# Fetch output
# ---------------------------------------------------------------------------

class TestFetchOutput:
    async def test_fetch_output_success(self, make_adapter):
        adapter = make_adapter()
        mock_store = AsyncMock()
        adapter.session_store = mock_store
        adapter._active_sessions["node_a"] = MagicMock(terminal_id="term_1")

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(
                return_value=_mock_response(200, {"output": "Hello world"}),
            )
            client.post = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            raw_output, truncated = await adapter._fetch_output("term_1")
            assert raw_output == "Hello world"
            assert truncated is False
            mock_store.complete_cao_session.assert_awaited_once_with("term_1")
            assert "node_a" not in adapter._active_sessions

    async def test_fetch_output_truncation_detected(self, make_adapter):
        adapter = make_adapter()
        adapter._active_sessions["node_a"] = MagicMock(terminal_id="term_1")
        # Build output with exactly 200 lines
        long_output = "\n".join(f"line {i}" for i in range(200))

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(
                return_value=_mock_response(200, {"output": long_output}),
            )
            client.post = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            raw_output, truncated = await adapter._fetch_output("term_1")
            assert raw_output == long_output
            assert truncated is True

    async def test_fetch_output_exit_only_no_delete(self, make_adapter):
        """Happy path should POST exit but NOT call DELETE on terminal."""
        adapter = make_adapter()
        mock_store = AsyncMock()
        adapter.session_store = mock_store
        adapter._active_sessions["node_a"] = MagicMock(terminal_id="term_1")

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(
                return_value=_mock_response(200, {"output": "result"}),
            )
            client.post = AsyncMock(return_value=_mock_response(200))
            client.delete = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            await adapter._fetch_output("term_1")

            # POST exit MUST be called
            client.post.assert_awaited_once_with("/terminals/term_1/exit")
            # DELETE MUST NOT be called in happy path
            client.delete.assert_not_awaited()


# ---------------------------------------------------------------------------
# Parse output
# ---------------------------------------------------------------------------

class TestParseOutput:
    def test_parse_text(self, make_adapter):
        adapter = make_adapter(cao_config=CaoConfig(output_format="text"))
        assert adapter._parse_output("hello") == "hello"

    def test_parse_json(self, make_adapter):
        adapter = make_adapter(cao_config=CaoConfig(output_format="json"))
        result = adapter._parse_output('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_invalid(self, make_adapter):
        adapter = make_adapter(cao_config=CaoConfig(output_format="json"))
        with pytest.raises(CAOOutputParseError, match="invalid JSON"):
            adapter._parse_output("not json")

    def test_parse_auto_json(self, make_adapter):
        adapter = make_adapter(cao_config=CaoConfig(output_format="auto"))
        result = adapter._parse_output('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_auto_text_fallback(self, make_adapter):
        adapter = make_adapter(cao_config=CaoConfig(output_format="auto"))
        result = adapter._parse_output("plain text output")
        assert result == "plain text output"

    def test_parse_json_with_output_field(self, make_adapter):
        adapter = make_adapter(
            cao_config=CaoConfig(output_format="json", output_field="$.result"),
        )
        result = adapter._parse_output('{"result": "approved", "details": "ok"}')
        assert result == "approved"

    def test_parse_json_output_field_no_match(self, make_adapter):
        adapter = make_adapter(
            cao_config=CaoConfig(output_format="json", output_field="$.missing"),
        )
        with pytest.raises(CAOOutputParseError, match="matched nothing"):
            adapter._parse_output('{"result": "approved"}')


# ---------------------------------------------------------------------------
# Build artifacts
# ---------------------------------------------------------------------------

class TestBuildArtifacts:
    def test_build_artifacts_text(self):
        artifacts = CAOAdapter._build_artifacts(
            "review", "run_1", "raw stdout", "parsed text", ["art_prev"],
        )
        assert len(artifacts) == 2
        assert artifacts[0].id == "review_cao_raw"
        assert artifacts[0].type == "cao_raw_output"
        assert artifacts[0].content == "raw stdout"

        assert artifacts[1].id == "review_cao_output"
        assert artifacts[1].type == "cao_output"
        assert artifacts[1].content == "parsed text"
        assert artifacts[1].lineage.derived_from == ["art_prev"]

    def test_build_artifacts_json(self):
        artifacts = CAOAdapter._build_artifacts(
            "n1", "run_1", '{"a":1}', {"a": 1}, [],
        )
        assert artifacts[1].type == "json"
        assert artifacts[1].content == {"a": 1}

    def test_build_artifacts_truncated(self):
        artifacts = CAOAdapter._build_artifacts(
            "n1", "run_1", "long output", "long output", [],
            possibly_truncated=True,
        )
        raw = artifacts[0]
        assert isinstance(raw.content, dict)
        assert raw.content["possibly_truncated"] is True
        assert raw.content["output"] == "long output"
        assert raw.content["truncation_limit"] == 200


# ---------------------------------------------------------------------------
# Full execute
# ---------------------------------------------------------------------------

class TestExecute:
    async def test_execute_full_handoff(self, make_adapter, task, input_artifacts):
        adapter = make_adapter()
        adapter.cao_config.min_wait_seconds = 1
        CAOAdapter._run_sessions.clear()
        CAOAdapter._run_session_locks.clear()
        mock_store = AsyncMock()
        adapter.session_store = mock_store

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()

            # Sequence: health, init, baseline, poll (min_wait), poll (done), fetch
            client.get = AsyncMock(side_effect=[
                # _check_health
                _mock_response(200, {"status": "ok"}),
                # _wait_for_init
                _mock_response(200, {"status": "idle"}),
                # baseline output capture (before task sent — empty)
                _mock_response(200, {"output": ""}),
                # _poll_until_done: during min_wait
                _mock_response(200, {"status": "completed"}),
                # _poll_until_done: past min_wait → completed → return
                _mock_response(200, {"status": "completed"}),
                # _fetch_output
                _mock_response(200, {"output": "Review complete: LGTM"}),
            ])
            client.post = AsyncMock(side_effect=[
                # _get_or_create_session: create session (first node in run)
                _mock_response(201, {"id": "term_abc"}),
                # send task
                _mock_response(200, {"success": True}),
                # exit
                _mock_response(200, {"success": True}),
            ])
            mock_client.return_value = client

            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                result = await adapter.execute(task, input_artifacts, "trace_1")

            assert len(result.artifacts) == 2
            assert result.artifacts[0].type == "cao_raw_output"
            assert result.artifacts[1].content == "Review complete: LGTM"
            assert result.cost is not None
            assert result.cost.cost == 0.0
            assert result.cost.source == "subscription_based"
            assert result.cost.model == "cao/claude_code"

    async def test_execute_server_unavailable(self, make_adapter, task, input_artifacts):
        adapter = make_adapter()
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.return_value = client

            with pytest.raises(CAOServerUnavailableError):
                await adapter.execute(task, input_artifacts, "trace_1")

    async def test_execute_profile_not_found(self, make_adapter, task, input_artifacts):
        adapter = make_adapter(profile="nonexistent")
        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.get = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))
            mock_client.return_value = client

            with pytest.raises(CAOProfileNotFoundError):
                await adapter.execute(task, input_artifacts, "trace_1")


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class TestCancel:
    async def test_cancel_no_active_session(self, make_adapter):
        adapter = make_adapter()
        await adapter.cancel("run_abc_review")  # should not raise

    async def test_cancel_with_active_session(self, make_adapter):
        adapter = make_adapter()
        adapter._active_sessions["review"] = MagicMock(terminal_id="term_1", node_name="review")
        mock_store = AsyncMock()
        adapter.session_store = mock_store

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(return_value=_mock_response(200))
            client.delete = AsyncMock(return_value=_mock_response(200))
            mock_client.return_value = client

            await adapter.cancel("run_abc_review")

            client.post.assert_awaited()
            client.delete.assert_awaited()
            mock_store.complete_cao_session.assert_awaited_once_with("term_1")
            assert "review" not in adapter._active_sessions

    async def test_cancel_swallows_errors(self, make_adapter):
        adapter = make_adapter()
        adapter._active_sessions["review"] = MagicMock(terminal_id="term_1", node_name="review")

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
            client.delete = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.return_value = client

            await adapter.cancel("run_abc_review")  # should not raise

    async def test_cancel_fallback_suffix_match(self, make_adapter):
        """cancel() finds session by node_name suffix when exact key doesn't match."""
        adapter = make_adapter()
        adapter._active_sessions["review"] = MagicMock(terminal_id="term_1", node_name="review")

        with patch.object(adapter, "_cleanup_terminal", new_callable=AsyncMock) as mock_cleanup:
            await adapter.cancel("run_abc_review")
            mock_cleanup.assert_awaited_once_with("term_1")

    async def test_parallel_sessions_cancel_correct(self, make_adapter):
        """Two nodes with same profile — cancel only affects the correct session."""
        adapter = make_adapter()
        adapter._active_sessions["node_a"] = MagicMock(terminal_id="term_1", node_name="node_a")
        adapter._active_sessions["node_b"] = MagicMock(terminal_id="term_2", node_name="node_b")

        with patch.object(adapter, "_cleanup_terminal", new_callable=AsyncMock) as mock_cleanup:
            await adapter.cancel("run_1_node_a")
            mock_cleanup.assert_awaited_once_with("term_1")

        # node_b session should still be present (cleanup_terminal removes by terminal_id)
        assert "node_b" in adapter._active_sessions


# ---------------------------------------------------------------------------
# Shared sessions (run-level session reuse)
# ---------------------------------------------------------------------------

class TestSharedSessions:
    async def test_shared_session_first_node_creates_session(self, make_adapter):
        """First CAO node in a run creates a new session."""
        CAOAdapter._run_sessions.clear()
        CAOAdapter._run_session_locks.clear()
        adapter = make_adapter()
        mock_store = AsyncMock()
        adapter.session_store = mock_store

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(
                return_value=_mock_response(201, {"id": "term_001"}),
            )
            mock_client.return_value = client

            session = await adapter._get_or_create_session("run_x", "node_a")

            assert session.terminal_id == "term_001"
            assert session.session_name == "binex-run_x"
            assert session.run_id == "run_x"
            assert "run_x" in CAOAdapter._run_sessions
            assert CAOAdapter._run_sessions["run_x"] == "binex-run_x"
            # Should have posted to /sessions (not /sessions/.../terminals)
            client.post.assert_awaited_once()
            call_args = client.post.call_args
            assert call_args[0][0] == "/sessions"

    async def test_shared_session_second_node_reuses(self, make_adapter):
        """Second CAO node reuses existing session, posts to terminals endpoint."""
        CAOAdapter._run_sessions.clear()
        CAOAdapter._run_session_locks.clear()
        adapter = make_adapter()
        mock_store = AsyncMock()
        adapter.session_store = mock_store

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(side_effect=[
                _mock_response(201, {"id": "term_001"}),
                _mock_response(201, {"id": "term_002"}),
            ])
            mock_client.return_value = client

            session_a = await adapter._get_or_create_session("run_y", "node_a")
            session_b = await adapter._get_or_create_session("run_y", "node_b")

            # Both have the same session_name but different terminal_ids
            assert session_a.session_name == session_b.session_name == "binex-run_y"
            assert session_a.terminal_id == "term_001"
            assert session_b.terminal_id == "term_002"

            # First call: POST /sessions, second: POST /sessions/cao-binex-run_y/terminals
            calls = client.post.call_args_list
            assert len(calls) == 2
            assert calls[0][0][0] == "/sessions"
            assert calls[1][0][0] == "/sessions/cao-binex-run_y/terminals"

    async def test_shared_session_different_runs_separate(self, make_adapter):
        """Different run_ids get separate sessions."""
        CAOAdapter._run_sessions.clear()
        CAOAdapter._run_session_locks.clear()
        adapter = make_adapter()

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(side_effect=[
                _mock_response(201, {"id": "term_r1"}),
                _mock_response(201, {"id": "term_r2"}),
            ])
            mock_client.return_value = client

            s1 = await adapter._get_or_create_session("run_1", "node_a")
            s2 = await adapter._get_or_create_session("run_2", "node_b")

            assert s1.session_name == "binex-run_1"
            assert s2.session_name == "binex-run_2"
            # Both should create new sessions via POST /sessions
            calls = client.post.call_args_list
            assert calls[0][0][0] == "/sessions"
            assert calls[1][0][0] == "/sessions"

    async def test_shared_session_sqlite_persistence_with_session_name(self, make_adapter):
        """Session name is passed to SQLite store for crash recovery."""
        CAOAdapter._run_sessions.clear()
        CAOAdapter._run_session_locks.clear()
        adapter = make_adapter()
        mock_store = AsyncMock()
        adapter.session_store = mock_store

        with patch.object(adapter, "_get_client") as mock_client:
            client = AsyncMock()
            client.post = AsyncMock(
                return_value=_mock_response(201, {"id": "term_999"}),
            )
            mock_client.return_value = client

            await adapter._get_or_create_session("run_z", "node_x")

            mock_store.create_cao_session.assert_awaited_once_with(
                terminal_id="term_999",
                run_id="run_z",
                node_name="node_x",
                session_name="binex-run_z",
            )


# ---------------------------------------------------------------------------
# Close (full cleanup)
# ---------------------------------------------------------------------------

class TestClose:
    async def test_close_exits_active_terminals(self, make_adapter):
        """close() sends POST /terminals/{id}/exit for each active terminal."""
        adapter = make_adapter()
        from binex.adapters.cao import CAOSession
        adapter._active_sessions["node_a"] = CAOSession(
            terminal_id="term_1", session_name="binex-run_1",
            run_id="run_1", node_name="node_a",
        )
        adapter._active_sessions["node_b"] = CAOSession(
            terminal_id="term_2", session_name="binex-run_1",
            run_id="run_1", node_name="node_b",
        )
        client = AsyncMock()
        client.is_closed = False
        client.post = AsyncMock(return_value=_mock_response(200))
        client.delete = AsyncMock(return_value=_mock_response(200))
        client.aclose = AsyncMock()
        adapter._client = client

        CAOAdapter._run_sessions["run_1"] = "binex-run_1"
        CAOAdapter._run_session_locks["run_1"] = MagicMock()

        await adapter.close()

        # Should have called exit on both terminals
        exit_calls = [
            c for c in client.post.call_args_list
            if "/terminals/" in str(c) and "/exit" in str(c)
        ]
        assert len(exit_calls) == 2

    async def test_close_deletes_sessions(self, make_adapter):
        """close() sends DELETE /sessions/cao-{name} for each run."""
        adapter = make_adapter()
        from binex.adapters.cao import CAOSession
        adapter._active_sessions["node_a"] = CAOSession(
            terminal_id="term_1", session_name="binex-run_1",
            run_id="run_1", node_name="node_a",
        )
        client = AsyncMock()
        client.is_closed = False
        client.post = AsyncMock(return_value=_mock_response(200))
        client.delete = AsyncMock(return_value=_mock_response(200))
        client.aclose = AsyncMock()
        adapter._client = client

        CAOAdapter._run_sessions["run_1"] = "binex-run_1"
        CAOAdapter._run_session_locks["run_1"] = MagicMock()

        await adapter.close()

        client.delete.assert_awaited_once_with("/sessions/cao-binex-run_1")

    async def test_close_clears_class_state(self, make_adapter):
        """close() clears _active_sessions, _run_sessions, and _run_session_locks."""
        adapter = make_adapter()
        from binex.adapters.cao import CAOSession
        adapter._active_sessions["node_a"] = CAOSession(
            terminal_id="term_1", session_name="binex-run_1",
            run_id="run_1", node_name="node_a",
        )
        adapter._active_sessions["node_b"] = CAOSession(
            terminal_id="term_2", session_name="binex-run_2",
            run_id="run_2", node_name="node_b",
        )
        client = AsyncMock()
        client.is_closed = False
        client.post = AsyncMock(return_value=_mock_response(200))
        client.delete = AsyncMock(return_value=_mock_response(200))
        client.aclose = AsyncMock()
        adapter._client = client

        CAOAdapter._run_sessions["run_1"] = "binex-run_1"
        CAOAdapter._run_sessions["run_2"] = "binex-run_2"
        CAOAdapter._run_session_locks["run_1"] = MagicMock()
        CAOAdapter._run_session_locks["run_2"] = MagicMock()

        await adapter.close()

        assert len(adapter._active_sessions) == 0
        assert "run_1" not in CAOAdapter._run_sessions
        assert "run_2" not in CAOAdapter._run_sessions
        assert "run_1" not in CAOAdapter._run_session_locks
        assert "run_2" not in CAOAdapter._run_session_locks
        assert adapter._client is None

    async def test_close_marks_sessions_completed_in_sqlite(self, make_adapter):
        """close() calls complete_cao_session for each active terminal."""
        adapter = make_adapter()
        from binex.adapters.cao import CAOSession
        mock_store = AsyncMock()
        adapter.session_store = mock_store
        adapter._active_sessions["node_a"] = CAOSession(
            terminal_id="term_1", session_name="binex-run_1",
            run_id="run_1", node_name="node_a",
        )
        adapter._active_sessions["node_b"] = CAOSession(
            terminal_id="term_2", session_name="binex-run_1",
            run_id="run_1", node_name="node_b",
        )
        client = AsyncMock()
        client.is_closed = False
        client.post = AsyncMock(return_value=_mock_response(200))
        client.delete = AsyncMock(return_value=_mock_response(200))
        client.aclose = AsyncMock()
        adapter._client = client

        CAOAdapter._run_sessions["run_1"] = "binex-run_1"
        CAOAdapter._run_session_locks["run_1"] = MagicMock()

        await adapter.close()

        complete_calls = mock_store.complete_cao_session.call_args_list
        terminal_ids = {c[0][0] for c in complete_calls}
        assert terminal_ids == {"term_1", "term_2"}


# ---------------------------------------------------------------------------
# Adapter registry wiring
# ---------------------------------------------------------------------------

class TestAdapterRegistryWiring:
    def test_register_cao_adapter_passes_event_callback(self):
        from unittest.mock import patch

        from binex.cli.adapter_registry import _register_cao_adapter
        from binex.runtime.dispatcher import Dispatcher

        dispatcher = Dispatcher()
        callback = lambda e: None  # noqa: E731
        node = MagicMock()
        node.cao = CaoConfig()

        with patch("binex.settings.Settings") as MockSettings:
            s = MockSettings.return_value
            s.cao_server_url = "http://localhost:9889"
            s.cao_agent_store_dir = "/tmp/store"
            _register_cao_adapter(
                dispatcher, "cao://dev", node,
                session_store=None, event_callback=callback,
            )

        adapter = dispatcher._adapters["cao://dev"]
        assert adapter._event_callback is callback
        assert adapter._human_input_fn is not None
