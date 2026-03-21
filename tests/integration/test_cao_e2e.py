"""Integration tests for CAO adapter — mock CAO server, full execute lifecycle."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from binex.adapters.cao import (
    CAOAdapter,
    CAOAgentError,
    CAOServerUnavailableError,
)
from binex.models.artifact import Artifact, Lineage
from binex.models.task import TaskNode
from binex.models.workflow import CaoConfig
from binex.stores.backends.sqlite import SqliteExecutionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code=200, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=resp,
        )
    return resp


class MockCAOServer:
    """Simulates CAO server HTTP responses for a full handoff sequence."""

    def __init__(
        self,
        output: str = "Agent output here",
        init_polls: int = 1,
        task_polls: int = 1,
        fail_at: str | None = None,
    ):
        self.output = output
        self.init_polls = init_polls
        self.task_polls = task_polls
        self.fail_at = fail_at
        self._get_calls: list[str] = []
        self._post_calls: list[str] = []

    async def get(self, url: str, **kwargs) -> httpx.Response:
        self._get_calls.append(url)

        if self.fail_at == "health" and "/health" in url:
            raise httpx.ConnectError("server down")

        if "/health" in url:
            return _mock_response(200, {"status": "ok"})

        if "/terminals/" in url and "/output" in url:
            # Baseline capture (before task sent) returns empty;
            # subsequent output fetches return the real output.
            output_calls = [c for c in self._get_calls if "/output" in c]
            if len(output_calls) <= 1:
                return _mock_response(200, {"output": "", "mode": "last"})
            return _mock_response(200, {"output": self.output, "mode": "last"})

        if "/terminals/" in url:
            # Status polling
            term_polls = [c for c in self._get_calls if "/terminals/" in c and "/output" not in c]
            poll_count = len(term_polls)
            if self.fail_at == "task_error":
                return _mock_response(200, {"status": "error"})
            if poll_count <= self.init_polls:
                return _mock_response(200, {"status": "processing"})
            return _mock_response(200, {"status": "completed"})

        return _mock_response(200)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        self._post_calls.append(url)

        if "/sessions" in url and "/terminals" in url:
            return _mock_response(201, {"id": "term_e2e_123"})
        if "/sessions" in url:
            return _mock_response(201, {"name": "sess_e2e"})
        if "/input" in url:
            return _mock_response(200, {"success": True})
        if "/exit" in url:
            return _mock_response(200, {"success": True})

        return _mock_response(200)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        return _mock_response(200, {"success": True})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_agent_store(tmp_path):
    store = tmp_path / "agent-store"
    store.mkdir()
    (store / "e2e_agent.md").write_text("# E2E Test Agent")
    return str(store)


@pytest.fixture()
async def session_store(tmp_path):
    db_path = str(tmp_path / "e2e.db")
    store = SqliteExecutionStore(db_path)
    await store.initialize()
    yield store
    await store.close()


@pytest.fixture()
def task():
    return TaskNode(
        id="task_e2e",
        run_id="run_e2e",
        node_id="analysis",
        agent="cao://e2e_agent",
        system_prompt="Analyze the code",
    )


@pytest.fixture()
def input_artifacts():
    return [
        Artifact(
            id="art_input",
            run_id="run_e2e",
            type="code",
            content="def hello(): pass",
            lineage=Lineage(produced_by="code_gen"),
        ),
    ]


# ---------------------------------------------------------------------------
# Full handoff lifecycle
# ---------------------------------------------------------------------------

class TestCAOFullHandoff:
    async def test_complete_handoff_text_output(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        """Full happy path: text output."""
        mock_server = MockCAOServer(output="Analysis complete: no issues found")
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
            cao_config=CaoConfig(output_format="text"),
        )

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                result = await adapter.execute(task, input_artifacts, "trace_e2e")

        # Verify artifacts
        assert len(result.artifacts) == 2
        raw_art = result.artifacts[0]
        out_art = result.artifacts[1]
        assert raw_art.type == "cao_raw_output"
        assert raw_art.id == "analysis_cao_raw"
        assert "no issues found" in raw_art.content

        assert out_art.type == "cao_output"
        assert out_art.id == "analysis_cao_output"
        assert out_art.content == "Analysis complete: no issues found"
        assert out_art.lineage.derived_from == ["art_input"]

        # Verify cost
        assert result.cost is not None
        assert result.cost.cost == 0.0
        assert result.cost.source == "subscription_based"
        assert result.cost.model == "cao/claude_code"
        assert result.cost.run_id == "run_e2e"
        assert result.cost.task_id == "analysis"

        # Verify session was marked completed (soft delete)
        sessions = await session_store.get_cao_sessions()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "completed"

    async def test_complete_handoff_json_output(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        """Full happy path: JSON auto-detect."""
        json_output = json.dumps({"result": "approved", "score": 95})
        mock_server = MockCAOServer(output=json_output)
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
            cao_config=CaoConfig(output_format="auto"),
        )

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                result = await adapter.execute(task, input_artifacts, "trace_e2e")

        out_art = result.artifacts[1]
        assert out_art.type == "json"
        assert out_art.content == {"result": "approved", "score": 95}

    async def test_json_output_with_jsonpath_extraction(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        """JSON output with output_field JSONPath extraction."""
        json_output = json.dumps({"result": "approved", "details": {"score": 99}})
        mock_server = MockCAOServer(output=json_output)
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
            cao_config=CaoConfig(output_format="json", output_field="$.result"),
        )

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                result = await adapter.execute(task, input_artifacts, "trace_e2e")

        assert result.artifacts[1].content == "approved"

    async def test_custom_provider_in_cost_model(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        """Provider is reflected in cost record model field."""
        mock_server = MockCAOServer(output="done")
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
            cao_config=CaoConfig(provider="kiro_cli", output_format="text"),
        )

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                result = await adapter.execute(task, input_artifacts, "trace_e2e")

        assert result.cost.model == "cao/kiro_cli"


# ---------------------------------------------------------------------------
# Error scenarios
# ---------------------------------------------------------------------------

class TestCAOErrorScenarios:
    async def test_server_unavailable(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        mock_server = MockCAOServer(fail_at="health")
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
        )

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with pytest.raises(CAOServerUnavailableError):
                await adapter.execute(task, input_artifacts, "trace_e2e")

    async def test_agent_error_during_task(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        """Agent enters error state during task execution."""
        mock_server = MockCAOServer(fail_at="task_error")
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
        )

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(CAOAgentError):
                    await adapter.execute(task, input_artifacts, "trace_e2e")


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

class TestCAOSessionLifecycle:
    async def test_session_persisted_during_execution(
        self, tmp_agent_store, session_store, task, input_artifacts,
    ):
        """Session is saved to SQLite during execution and cleaned up after."""
        mock_server = MockCAOServer(output="done")
        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
        )

        sessions_during: list[dict] = []

        original_send = adapter._send_task

        async def _intercept_send(tid, t, arts):
            # Check sessions mid-execution
            s = await session_store.get_cao_sessions(status="active")
            sessions_during.extend(s)
            return await original_send(tid, t, arts)

        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            with patch.object(adapter, "_send_task", side_effect=_intercept_send):
                with patch("binex.adapters.cao.asyncio.sleep", new_callable=AsyncMock):
                    await adapter.execute(task, input_artifacts, "trace_e2e")

        # Session existed during execution
        assert len(sessions_during) == 1
        assert sessions_during[0]["status"] == "active"

        # Session marked completed after
        after = await session_store.get_cao_sessions()
        assert len(after) == 1
        assert after[0]["status"] == "completed"

    async def test_cancel_cleans_up_session(
        self, tmp_agent_store, session_store,
    ):
        """Cancel removes session from store."""
        await session_store.create_cao_session("term_cancel", "run_1", "node_1")

        adapter = CAOAdapter(
            profile="e2e_agent",
            server_url="http://localhost:9889",
            agent_store_dir=tmp_agent_store,
            session_store=session_store,
        )
        from binex.adapters.cao import CAOSession
        adapter._active_sessions = {"node_1": CAOSession(
            terminal_id="term_cancel",
            session_name="sess_1",
            run_id="run_1",
            node_name="node_1",
        )}

        mock_server = MockCAOServer()
        with patch.object(adapter, "_get_client") as mock_client:
            mock_client.return_value = mock_server
            await adapter.cancel("node_1")

        sessions = await session_store.get_cao_sessions()
        assert len(sessions) == 0
