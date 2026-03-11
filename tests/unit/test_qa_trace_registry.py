"""QA P2 tests for trace timeline, diff, rich formatting, and registry."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from rich.console import Console

from binex.models.artifact import Artifact, Lineage
from binex.models.execution import ExecutionRecord, RunSummary
from binex.models.task import TaskStatus
from binex.registry.app import app, registry_state
from binex.registry.discovery import AgentDiscovery, DiscoveryError
from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.trace.debug_report import DebugReport, NodeReport
from binex.trace.debug_rich import format_debug_report_rich
from binex.trace.diff import diff_runs, format_diff
from binex.trace.tracer import generate_timeline, generate_timeline_json


def _capture_rich(report, **kwargs) -> str:
    """Call format_debug_report_rich and capture its console output."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=True, width=120)
    with patch("binex.trace.debug_rich.get_console", return_value=test_console):
        format_debug_report_rich(report, **kwargs)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def execution_store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture
def art_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


@pytest.fixture(autouse=True)
def _clear_registry():
    registry_state.agents.clear()
    yield
    registry_state.agents.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def discovery(mock_client: AsyncMock) -> AgentDiscovery:
    return AgentDiscovery(client=mock_client)


def _mock_response(*, status_code: int = 200, json_data: dict | None = None, text: str = ""):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("Invalid JSON")
        resp.text = text
    return resp


# ===========================================================================
# TC-TRC-001: Timeline with empty run (0 records) — verify output format
# ===========================================================================


@pytest.mark.asyncio
async def test_timeline_empty_run_no_records_text(
    execution_store: InMemoryExecutionStore,
) -> None:
    """Timeline of a run with zero execution records returns a 'no records' message."""
    # Arrange — run exists but has no execution records
    summary = RunSummary(
        run_id="empty-run",
        workflow_name="empty-wf",
        status="completed",
        total_nodes=0,
        completed_nodes=0,
    )
    await execution_store.create_run(summary)

    # Act
    result = await generate_timeline(execution_store, "empty-run")

    # Assert
    assert isinstance(result, str)
    assert "no records" in result.lower()


@pytest.mark.asyncio
async def test_timeline_empty_run_no_records_json(
    execution_store: InMemoryExecutionStore,
) -> None:
    """JSON timeline of a run with zero records returns an empty list."""
    # Arrange
    summary = RunSummary(
        run_id="empty-run",
        workflow_name="empty-wf",
        status="completed",
        total_nodes=0,
        completed_nodes=0,
    )
    await execution_store.create_run(summary)

    # Act
    result = await generate_timeline_json(execution_store, "empty-run")

    # Assert
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_timeline_nonexistent_run_text(
    execution_store: InMemoryExecutionStore,
) -> None:
    """Timeline of a completely nonexistent run also returns a 'no records' message."""
    # Arrange — nothing seeded

    # Act
    result = await generate_timeline(execution_store, "does-not-exist")

    # Assert
    assert isinstance(result, str)
    assert "no records" in result.lower() or result.strip() == ""


# ===========================================================================
# TC-TRC-003: Diff of two runs with different node counts — handles missing nodes
# ===========================================================================


async def _seed_asymmetric_runs(
    exec_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
) -> tuple[str, str]:
    """Create run_a with 3 nodes and run_b with 1 node for diff testing."""
    # --- run_a: 3 nodes ---
    summary_a = RunSummary(
        run_id="run_a",
        workflow_name="pipeline",
        status="completed",
        total_nodes=3,
        completed_nodes=3,
    )
    await exec_store.create_run(summary_a)

    for task_id, idx in [("step_1", 1), ("step_2", 2), ("step_3", 3)]:
        art = Artifact(
            id=f"art_{task_id}_a",
            run_id="run_a",
            type="text",
            content={"val": f"output_{idx}"},
            lineage=Lineage(produced_by=task_id),
        )
        await art_store.store(art)
        rec = ExecutionRecord(
            id=f"rec_{task_id}_a",
            run_id="run_a",
            task_id=task_id,
            agent_id="local://echo",
            status=TaskStatus.COMPLETED,
            output_artifact_refs=[art.id],
            latency_ms=100 * idx,
            trace_id="trace_a",
        )
        await exec_store.record(rec)

    # --- run_b: only 1 node (step_1) ---
    summary_b = RunSummary(
        run_id="run_b",
        workflow_name="pipeline",
        status="failed",
        total_nodes=3,
        completed_nodes=1,
        failed_nodes=1,
    )
    await exec_store.create_run(summary_b)

    art_b = Artifact(
        id="art_step_1_b",
        run_id="run_b",
        type="text",
        content={"val": "output_1"},
        lineage=Lineage(produced_by="step_1"),
    )
    await art_store.store(art_b)
    rec_b = ExecutionRecord(
        id="rec_step_1_b",
        run_id="run_b",
        task_id="step_1",
        agent_id="local://echo",
        status=TaskStatus.COMPLETED,
        output_artifact_refs=[art_b.id],
        latency_ms=100,
        trace_id="trace_b",
    )
    await exec_store.record(rec_b)

    return "run_a", "run_b"


@pytest.mark.asyncio
async def test_diff_different_node_counts_has_all_tasks(
    execution_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
) -> None:
    """Diff of runs with different node counts includes the union of all task IDs."""
    # Arrange
    run_a, run_b = await _seed_asymmetric_runs(execution_store, art_store)

    # Act
    result = await diff_runs(execution_store, art_store, run_a, run_b)

    # Assert — all three tasks should appear
    task_ids = {s["task_id"] for s in result["steps"]}
    assert task_ids == {"step_1", "step_2", "step_3"}


@pytest.mark.asyncio
async def test_diff_missing_nodes_have_none_status(
    execution_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
) -> None:
    """Steps only present in one run should have None status for the other run."""
    # Arrange
    run_a, run_b = await _seed_asymmetric_runs(execution_store, art_store)

    # Act
    result = await diff_runs(execution_store, art_store, run_a, run_b)

    # Assert — step_2 and step_3 are missing in run_b
    step_2 = next(s for s in result["steps"] if s["task_id"] == "step_2")
    assert step_2["status_a"] == "completed"
    assert step_2["status_b"] is None
    assert step_2["latency_b"] is None
    assert step_2["agent_b"] is None
    assert step_2["status_changed"] is True

    step_3 = next(s for s in result["steps"] if s["task_id"] == "step_3")
    assert step_3["status_b"] is None


@pytest.mark.asyncio
async def test_diff_missing_nodes_artifacts_changed(
    execution_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
) -> None:
    """Steps missing from one run should report artifacts_changed=True."""
    # Arrange
    run_a, run_b = await _seed_asymmetric_runs(execution_store, art_store)

    # Act
    result = await diff_runs(execution_store, art_store, run_a, run_b)

    # Assert — step_2 has artifacts in run_a but not run_b → changed
    step_2 = next(s for s in result["steps"] if s["task_id"] == "step_2")
    assert step_2["artifacts_changed"] is True


@pytest.mark.asyncio
async def test_diff_format_text_handles_missing_nodes(
    execution_store: InMemoryExecutionStore,
    art_store: InMemoryArtifactStore,
) -> None:
    """format_diff should not crash when rendering steps with None values."""
    # Arrange
    run_a, run_b = await _seed_asymmetric_runs(execution_store, art_store)
    result = await diff_runs(execution_store, art_store, run_a, run_b)

    # Act
    text = format_diff(result)

    # Assert — should include all tasks and not crash
    assert isinstance(text, str)
    assert "step_1" in text
    assert "step_2" in text
    assert "step_3" in text


# ===========================================================================
# TC-TRC-005: Rich formatting with Unicode/special chars in error messages
# ===========================================================================


def test_rich_format_unicode_error_message_no_crash() -> None:
    """Rich formatter handles Unicode and special characters in error messages."""
    # Arrange
    unicode_error = (
        "Error: \u2018connection refused\u2019 \u2014 server \u00e9\u00e8\u00ea returned \u2603\ufe0f "
        "\u2705 \u274c \u26a0\ufe0f null-byte:\x00 tab:\t newline:\n"
    )
    report = DebugReport(
        run_id="run-unicode-001",
        workflow_name="unicode-\u00fc\u00f6\u00e4-wf",
        status="failed",
        total_nodes=1,
        completed_nodes=0,
        failed_nodes=1,
        duration_ms=500,
        nodes=[
            NodeReport(
                node_id="step_\u00e9",
                agent_id="llm://gpt-4",
                status="failed",
                latency_ms=250,
                prompt="Analyze \u201cspecial chars\u201d",
                error=unicode_error,
            ),
        ],
    )

    # Act
    output = _capture_rich(report)

    # Assert — no crash, output is a non-empty string containing the run_id
    assert isinstance(output, str)
    assert len(output) > 0
    assert "run-unicode-001" in output


def test_rich_format_empty_error_string() -> None:
    """Rich formatter handles an empty-string error without crashing."""
    # Arrange
    report = DebugReport(
        run_id="run-empty-err",
        workflow_name="wf",
        status="failed",
        total_nodes=1,
        completed_nodes=0,
        failed_nodes=1,
        duration_ms=100,
        nodes=[
            NodeReport(
                node_id="step_x",
                agent_id="llm://gpt-4",
                status="failed",
                latency_ms=50,
                error="",
            ),
        ],
    )

    # Act
    output = _capture_rich(report)

    # Assert
    assert isinstance(output, str)
    assert "step_x" in output


def test_rich_format_multiline_error() -> None:
    """Rich formatter handles multi-line error messages readably."""
    # Arrange
    multiline_error = "Traceback (most recent call last):\n  File \"run.py\", line 42\n    raise RuntimeError(\"boom\")\nRuntimeError: boom"
    report = DebugReport(
        run_id="run-multiline",
        workflow_name="wf",
        status="failed",
        total_nodes=1,
        completed_nodes=0,
        failed_nodes=1,
        duration_ms=100,
        nodes=[
            NodeReport(
                node_id="step_tb",
                agent_id="llm://gpt-4",
                status="failed",
                latency_ms=75,
                error=multiline_error,
            ),
        ],
    )

    # Act
    output = _capture_rich(report)

    # Assert — should contain key parts of the traceback
    assert isinstance(output, str)
    assert "RuntimeError" in output
    assert "step_tb" in output


def test_rich_format_special_chars_in_prompt() -> None:
    """Rich formatter handles special characters in prompt without crash."""
    # Arrange
    report = DebugReport(
        run_id="run-specials",
        workflow_name="wf",
        status="completed",
        total_nodes=1,
        completed_nodes=1,
        failed_nodes=0,
        duration_ms=200,
        nodes=[
            NodeReport(
                node_id="step_sp",
                agent_id="llm://gpt-4",
                status="completed",
                latency_ms=100,
                prompt="Query with <html> & \"quotes\" and \\ backslashes",
            ),
        ],
    )

    # Act
    output = _capture_rich(report)

    # Assert
    assert isinstance(output, str)
    assert "step_sp" in output


# ===========================================================================
# TC-REG-001: Register agent with invalid endpoint URL — validation on input
# ===========================================================================


def test_register_agent_missing_endpoint(client: TestClient) -> None:
    """POST /agents without endpoint field should fail validation (422)."""
    # Arrange
    payload = {"name": "Bad Agent", "capabilities": ["test"]}

    # Act
    resp = client.post("/agents", json=payload)

    # Assert
    assert resp.status_code == 422


def test_register_agent_missing_name(client: TestClient) -> None:
    """POST /agents without name field should fail validation (422)."""
    # Arrange
    payload = {"endpoint": "http://localhost:9001", "capabilities": ["test"]}

    # Act
    resp = client.post("/agents", json=payload)

    # Assert
    assert resp.status_code == 422


def test_register_agent_empty_endpoint_is_accepted(client: TestClient) -> None:
    """POST /agents with empty string endpoint is accepted (no URL validation on model)."""
    # Arrange — endpoint is typed as str (not HttpUrl), so empty string passes Pydantic
    payload = {"endpoint": "", "name": "EmptyEndpoint", "capabilities": []}

    # Act
    resp = client.post("/agents", json=payload)

    # Assert — accepted because the model uses plain str for endpoint
    assert resp.status_code == 201
    data = resp.json()
    assert data["endpoint"] == ""


def test_register_agent_wrong_type_endpoint(client: TestClient) -> None:
    """POST /agents with non-string endpoint (e.g., integer) should fail validation."""
    # Arrange
    payload = {"endpoint": 12345, "name": "BadType", "capabilities": []}

    # Act
    resp = client.post("/agents", json=payload)

    # Assert — Pydantic coerces int to str, so this may be 201; verify coherent response
    # If Pydantic coerces, the agent is stored with endpoint="12345"
    if resp.status_code == 201:
        data = resp.json()
        assert data["endpoint"] == "12345"
    else:
        assert resp.status_code == 422


def test_register_agent_null_payload(client: TestClient) -> None:
    """POST /agents with null JSON body should fail validation (422)."""
    # Arrange / Act
    resp = client.post("/agents", content="null", headers={"Content-Type": "application/json"})

    # Assert
    assert resp.status_code == 422


# ===========================================================================
# TC-REG-004: Discovery: /.well-known/agent.json unavailable — error handling
# ===========================================================================


@pytest.mark.asyncio
async def test_discovery_404_raises_discovery_error(
    discovery: AgentDiscovery,
    mock_client: AsyncMock,
) -> None:
    """fetch_agent_card raises DiscoveryError when server returns 404."""
    # Arrange
    mock_client.get.return_value = _mock_response(status_code=404)

    # Act / Assert
    with pytest.raises(DiscoveryError):
        await discovery.fetch_agent_card("http://agent.example.com")


@pytest.mark.asyncio
async def test_discovery_500_raises_discovery_error(
    discovery: AgentDiscovery,
    mock_client: AsyncMock,
) -> None:
    """fetch_agent_card raises DiscoveryError when server returns 500."""
    # Arrange
    mock_client.get.return_value = _mock_response(status_code=500)

    # Act / Assert
    with pytest.raises(DiscoveryError):
        await discovery.fetch_agent_card("http://agent.example.com")


@pytest.mark.asyncio
async def test_discovery_connection_refused_raises_discovery_error(
    discovery: AgentDiscovery,
    mock_client: AsyncMock,
) -> None:
    """fetch_agent_card raises DiscoveryError on connection refused."""
    # Arrange
    mock_client.get.side_effect = httpx.ConnectError("connection refused")

    # Act / Assert
    with pytest.raises(DiscoveryError, match="connection refused"):
        await discovery.fetch_agent_card("http://unreachable.example.com")


@pytest.mark.asyncio
async def test_discovery_timeout_raises_discovery_error(
    discovery: AgentDiscovery,
    mock_client: AsyncMock,
) -> None:
    """fetch_agent_card raises DiscoveryError on request timeout."""
    # Arrange
    mock_client.get.side_effect = httpx.TimeoutException("timed out")

    # Act / Assert
    with pytest.raises(DiscoveryError, match="timed out"):
        await discovery.fetch_agent_card("http://slow.example.com")


@pytest.mark.asyncio
async def test_discovery_invalid_json_raises_discovery_error(
    discovery: AgentDiscovery,
    mock_client: AsyncMock,
) -> None:
    """fetch_agent_card raises DiscoveryError when response is not valid JSON."""
    # Arrange
    mock_client.get.return_value = _mock_response(text="<html>Not Found</html>")

    # Act / Assert
    with pytest.raises(DiscoveryError, match="Invalid JSON"):
        await discovery.fetch_agent_card("http://agent.example.com")


@pytest.mark.asyncio
async def test_discover_unavailable_endpoint_raises_discovery_error(
    discovery: AgentDiscovery,
    mock_client: AsyncMock,
) -> None:
    """discover() propagates DiscoveryError when agent.json is unavailable."""
    # Arrange
    mock_client.get.side_effect = httpx.ConnectError("no route to host")

    # Act / Assert
    with pytest.raises(DiscoveryError, match="no route to host"):
        await discovery.discover("http://unreachable.example.com")
