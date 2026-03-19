"""CAO (CLI Agent Orchestrator) adapter — Handoff pattern integration.

Integrates AWS Labs' CLI Agent Orchestrator as a first-class Binex adapter.
Implements the Handoff pattern: synchronous REST-based execution with adaptive
polling, two-artifact output (raw + parsed), and SQLite session registry for
crash recovery.

Agent URI: ``cao://profile_name``

CAO Handoff sequence:
  1. POST /sessions — create session
  2. POST /sessions/{name}/terminals — create worker terminal
  3. GET /terminals/{id} — poll until idle (init complete)
  4. POST /terminals/{id}/input — send task
  5. GET /terminals/{id} — poll until idle/completed (task done)
  6. GET /terminals/{id}/output — fetch result
  7. POST /terminals/{id}/exit — graceful cleanup
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Literal
from uuid import uuid4

import httpx

if TYPE_CHECKING:
    from binex.stores.backends.sqlite import SqliteExecutionStore

from binex.models.agent import AgentHealth
from binex.models.artifact import Artifact, Lineage
from binex.models.cost import CostRecord, ExecutionResult
from binex.models.task import TaskNode
from binex.models.workflow import CaoConfig

logger = logging.getLogger(__name__)

__all__ = [
    "CAOAdapter",
    "CAOAgentError",
    "CAOOutputParseError",
    "CAOProfileNotFoundError",
    "CAOServerUnavailableError",
    "CAOSession",
    "CAOTimeoutError",
]


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class CAOServerUnavailableError(RuntimeError):
    """Raised when the CAO server is unreachable."""


class CAOProfileNotFoundError(RuntimeError):
    """Raised when the requested agent profile is not installed."""


class CAOTimeoutError(RuntimeError):
    """Raised when a CAO agent exceeds its timeout limit."""


class CAOAgentError(RuntimeError):
    """Raised when the CAO agent enters an error state."""


class CAOOutputParseError(RuntimeError):
    """Raised when the agent output cannot be parsed as expected format."""


# ---------------------------------------------------------------------------
# Terminal done statuses
# ---------------------------------------------------------------------------

_DONE_STATUSES = frozenset({"idle", "completed"})
_INIT_TIMEOUT_S = 120
_INIT_POLL_INTERVAL_S = 1.0
_TMUX_HISTORY_LINES = 200


# ---------------------------------------------------------------------------
# Session model
# ---------------------------------------------------------------------------

@dataclass
class CAOSession:
    """In-memory representation of an active CAO terminal session."""

    terminal_id: str
    session_name: str
    run_id: str
    node_name: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: Literal["active", "completed", "orphaned"] = "active"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class CAOAdapter:
    """Binex adapter for CAO Handoff pattern.

    Implements the ``AgentAdapter`` protocol. Constructed by
    ``register_workflow_adapters`` when the agent string starts with ``cao://``.
    """

    _run_sessions: ClassVar[dict[str, str]] = {}  # run_id → session_name
    _run_session_locks: ClassVar[dict[str, asyncio.Lock]] = {}

    def __init__(
        self,
        profile: str,
        server_url: str,
        agent_store_dir: str,
        session_store: SqliteExecutionStore | None = None,
        cao_config: CaoConfig | None = None,
        event_callback: Callable | None = None,
        human_input_fn: Callable | None = None,
    ) -> None:
        self.profile = profile
        self.server_url = server_url.rstrip("/")
        self.agent_store_dir = agent_store_dir
        self.session_store = session_store
        self.cao_config = cao_config or CaoConfig()
        self._event_callback = event_callback
        self._human_input_fn = human_input_fn
        self._human_prompt_count: int = 0
        self._active_sessions: dict[str, CAOSession] = {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.server_url, timeout=30.0,
            )
        return self._client

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> AgentHealth:
        """Check CAO server health via GET /health."""
        try:
            client = await self._get_client()
            resp = await client.get("/health")
            if resp.status_code == 200:
                return AgentHealth.ALIVE
            return AgentHealth.DEGRADED
        except httpx.HTTPError:
            return AgentHealth.DOWN

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------

    async def _check_health(self) -> None:
        """Verify the CAO server is reachable. Raises on failure."""
        try:
            client = await self._get_client()
            resp = await client.get("/health")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise CAOServerUnavailableError(
                f"CAO server unavailable at {self.server_url}. "
                f"Start it with: cao-server start — {exc}"
            ) from exc

    def _check_profile(self) -> None:
        """Verify the agent profile .md file exists on disk."""
        profile_path = os.path.join(self.agent_store_dir, f"{self.profile}.md")
        if not os.path.isfile(profile_path):
            raise CAOProfileNotFoundError(
                f"CAO profile '{self.profile}' not found at {profile_path}. "
                f"Install it with: cao profile install {self.profile}"
            )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def _get_or_create_session(self, run_id: str, node_name: str) -> CAOSession:
        """Get existing or create new CAO session + terminal.

        Multiple CAO nodes in the same run share one CAO session with
        separate terminals. A per-run lock prevents race conditions when
        two nodes start concurrently.
        """
        session_name = f"binex-{run_id}"
        provider = self.cao_config.provider or "claude_code"

        # Per-run lock to prevent race conditions
        if run_id not in self._run_session_locks:
            self._run_session_locks[run_id] = asyncio.Lock()

        async with self._run_session_locks[run_id]:
            client = await self._get_client()

            if run_id in self._run_sessions:
                # Session exists — add terminal to existing session
                resp = await client.post(
                    f"/sessions/cao-{session_name}/terminals",
                    data={"provider": provider, "agent_profile": self.profile},
                )
            else:
                # First CAO node in this run — create new session
                resp = await client.post(
                    "/sessions",
                    params={
                        "provider": provider,
                        "agent_profile": self.profile,
                        "session_name": session_name,
                    },
                )
                self._run_sessions[run_id] = session_name

            resp.raise_for_status()
            data = resp.json()
            terminal_id = str(data.get("id", ""))

        session = CAOSession(
            terminal_id=terminal_id,
            session_name=session_name,
            run_id=run_id,
            node_name=node_name,
        )
        self._active_sessions[node_name] = session

        # Persist to SQLite for crash recovery
        if self.session_store is not None:
            try:
                await self.session_store.create_cao_session(
                    terminal_id=terminal_id,
                    run_id=run_id,
                    node_name=node_name,
                    session_name=session_name,
                )
            except Exception:
                # SQLite write failed — cleanup the terminal we just created
                logger.error(
                    "Failed to persist CAO session %s to SQLite; cleaning up terminal",
                    terminal_id,
                )
                await self._cleanup_terminal(terminal_id)
                raise

        return session

    async def _wait_for_init(self, terminal_id: str) -> None:
        """Poll until terminal reaches idle/completed (init done). Max 120s."""
        client = await self._get_client()
        elapsed = 0.0
        while elapsed < _INIT_TIMEOUT_S:
            resp = await client.get(f"/terminals/{terminal_id}")
            resp.raise_for_status()
            status = resp.json().get("status", "")
            if status in _DONE_STATUSES:
                return
            if status == "error":
                raise CAOAgentError(
                    f"CAO terminal {terminal_id} entered error state during init"
                )
            await asyncio.sleep(_INIT_POLL_INTERVAL_S)
            elapsed += _INIT_POLL_INTERVAL_S

        raise CAOTimeoutError(
            f"CAO terminal {terminal_id} did not initialize within {_INIT_TIMEOUT_S}s"
        )

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    async def _send_task(
        self, terminal_id: str, task: TaskNode, input_artifacts: list[Artifact],
    ) -> None:
        """Serialize inputs and send task to the CAO terminal."""
        # Build task message from system_prompt + input artifacts
        parts: list[str] = []
        if task.system_prompt:
            parts.append(task.system_prompt)

        for art in input_artifacts:
            content = art.content
            if isinstance(content, dict):
                content = json.dumps(content, ensure_ascii=False)
            elif not isinstance(content, str):
                content = str(content)
            parts.append(content)

        # Fallback: use node inputs if no artifacts
        if not parts and task.inputs:
            for key, val in task.inputs.items():
                if isinstance(val, str):
                    parts.append(val)
                else:
                    parts.append(json.dumps(val, ensure_ascii=False))

        message = "\n\n".join(parts) if parts else f"Execute profile {self.profile}"

        client = await self._get_client()
        resp = await client.post(
            f"/terminals/{terminal_id}/input",
            data={"message": message},
        )
        resp.raise_for_status()

    async def _poll_until_done(self, terminal_id: str, timeout_s: float) -> None:
        """Poll terminal status with tiered intervals until done or timeout.

        The CAO server uses ``idle`` for two distinct states:
        - pre-processing idle: terminal ready, task not yet started
        - post-processing idle: task completed, output available

        These are indistinguishable via status alone.  To tell them apart we
        probe the output endpoint: a 200 response means output exists (done),
        a 404 means no Claude Code response yet (still pre-processing).

        Fast tasks may also skip ``processing`` entirely (idle → completed),
        so we cannot rely on seeing ``processing`` before accepting done.
        """
        client = await self._get_client()
        elapsed = 0.0
        _saw_processing = False

        # Tiered polling: fast at start, slower for long tasks
        poll_tiers = [(30.0, 2.0), (120.0, 5.0), (float("inf"), 15.0)]

        while elapsed < timeout_s:
            resp = await client.get(f"/terminals/{terminal_id}")
            resp.raise_for_status()
            status = resp.json().get("status", "")

            if status == "error":
                raise CAOAgentError(
                    f"CAO agent on terminal {terminal_id} entered error state"
                )

            if status == "waiting_user_answer":
                self._human_prompt_count += 1
                if self._human_prompt_count > self.cao_config.max_human_prompts:
                    raise CAOAgentError(
                        f"CAO agent on terminal {terminal_id} exceeded "
                        f"max_human_prompts ({self.cao_config.max_human_prompts})"
                    )

                # Emit event for UI
                if self._event_callback is not None:
                    event = {
                        "type": "cao:waiting_input",
                        "terminal_id": terminal_id,
                        "prompt_number": self._human_prompt_count,
                    }
                    cb_result = self._event_callback(event)
                    if asyncio.iscoroutine(cb_result):
                        await cb_result

                # Get human input
                if self._human_input_fn is not None:
                    answer = self._human_input_fn(self.profile, terminal_id)
                    if asyncio.iscoroutine(answer):
                        answer = await answer
                else:
                    # CLI fallback
                    import click
                    answer = click.prompt(
                        f"CAO agent '{self.profile}' is waiting for input"
                    )

                # Send answer back to CAO terminal
                await client.post(
                    f"/terminals/{terminal_id}/input",
                    data={"message": str(answer)},
                )
                continue  # Resume polling

            if status == "processing":
                _saw_processing = True

            if status in _DONE_STATUSES:
                if _saw_processing:
                    return  # Saw processing → done for sure
                # Haven't seen processing yet — check output to distinguish
                # pre-processing idle from post-processing idle
                out_resp = await client.get(
                    f"/terminals/{terminal_id}/output",
                    params={"mode": "last"},
                )
                if out_resp.status_code == 200 and out_resp.json().get("output", ""):
                    return  # Non-empty output — task is done
                logger.debug(
                    "Terminal %s idle but no output yet, waiting for task to start",
                    terminal_id,
                )
            elif status != "processing":
                logger.warning("Unknown CAO terminal status: %s", status)

            # Select poll interval from tier based on elapsed time
            poll_interval = poll_tiers[-1][1]
            for threshold, interval in poll_tiers:
                if elapsed < threshold:
                    poll_interval = interval
                    break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise CAOTimeoutError(
            f"CAO agent on terminal {terminal_id} timed out after "
            f"{timeout_s:.0f}s (limit: {self.cao_config.timeout_minutes}m)"
        )

    # ------------------------------------------------------------------
    # Output handling
    # ------------------------------------------------------------------

    async def _fetch_output(self, terminal_id: str) -> tuple[str, bool]:
        """Fetch raw output from terminal, then exit + cleanup.

        Returns (raw_output, possibly_truncated).
        """
        client = await self._get_client()

        resp = await client.get(
            f"/terminals/{terminal_id}/output",
            params={"mode": "last"},
        )
        resp.raise_for_status()
        data = resp.json()
        raw_output: str = data.get("output", "")

        # Detect tmux 200-line truncation
        newlines = raw_output.count("\n")
        has_trailing = raw_output.endswith("\n") if raw_output else True
        line_count = newlines + (0 if has_trailing else 1)
        possibly_truncated = line_count >= _TMUX_HISTORY_LINES
        if possibly_truncated:
            logger.warning(
                "CAO output from terminal %s hit %d lines (tmux cap: %d) — "
                "output may be truncated",
                terminal_id, line_count, _TMUX_HISTORY_LINES,
            )

        # Graceful exit
        try:
            await client.post(f"/terminals/{terminal_id}/exit")
        except httpx.HTTPError:
            logger.debug("Failed to send exit to terminal %s", terminal_id)

        # Mark session completed in store
        if self.session_store is not None:
            await self.session_store.complete_cao_session(terminal_id)

        # Remove session by terminal_id
        self._active_sessions = {
            k: v for k, v in self._active_sessions.items()
            if v.terminal_id != terminal_id
        }
        return raw_output, possibly_truncated

    def _parse_output(self, raw_output: str) -> Any:
        """Parse raw output according to output_format + output_field config."""
        fmt = self.cao_config.output_format

        if fmt == "text":
            return raw_output

        if fmt == "json":
            return self._parse_json_output(raw_output)

        # auto: try JSON first, fall back to text
        try:
            return self._parse_json_output(raw_output)
        except CAOOutputParseError:
            return raw_output

    def _parse_json_output(self, raw_output: str) -> Any:
        """Parse as JSON, optionally extracting a field via JSONPath."""
        try:
            parsed = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise CAOOutputParseError(
                f"Expected JSON output but got invalid JSON: {exc}"
            ) from exc

        if self.cao_config.output_field:
            return self._extract_jsonpath(parsed, self.cao_config.output_field)

        return parsed

    @staticmethod
    def _extract_jsonpath(data: Any, expression: str) -> Any:
        """Extract value using JSONPath expression."""
        from jsonpath_ng import parse as jp_parse

        matches = jp_parse(expression).find(data)
        if not matches:
            raise CAOOutputParseError(
                f"JSONPath '{expression}' matched nothing in output"
            )
        if len(matches) == 1:
            return matches[0].value
        return [m.value for m in matches]

    # ------------------------------------------------------------------
    # Artifact construction
    # ------------------------------------------------------------------

    @staticmethod
    def _build_artifacts(
        node_id: str,
        run_id: str,
        raw_output: str,
        parsed_output: Any,
        input_artifact_ids: list[str],
        *,
        possibly_truncated: bool = False,
    ) -> list[Artifact]:
        """Build cao_raw_output + cao_output artifacts."""
        derived = input_artifact_ids

        raw_content: Any = raw_output
        if possibly_truncated:
            raw_content = {
                "output": raw_output,
                "possibly_truncated": True,
                "truncation_limit": _TMUX_HISTORY_LINES,
            }

        raw_artifact = Artifact(
            id=f"{node_id}_cao_raw",
            run_id=run_id,
            type="cao_raw_output",
            content=raw_content,
            lineage=Lineage(produced_by=node_id, derived_from=derived),
        )

        # Determine output type
        output_type = "json" if isinstance(parsed_output, (dict, list)) else "cao_output"

        output_artifact = Artifact(
            id=f"{node_id}_cao_output",
            run_id=run_id,
            type=output_type,
            content=parsed_output,
            lineage=Lineage(produced_by=node_id, derived_from=derived),
        )

        return [raw_artifact, output_artifact]

    # ------------------------------------------------------------------
    # Execute (main orchestration)
    # ------------------------------------------------------------------

    async def execute(
        self,
        task: TaskNode,
        input_artifacts: list[Artifact],
        trace_id: str,
    ) -> ExecutionResult:
        """Execute CAO Handoff — full lifecycle."""
        start_time = time.monotonic()
        self._human_prompt_count = 0

        # Pre-flight
        await self._check_health()
        self._check_profile()

        # Get or create shared session + terminal
        session = await self._get_or_create_session(task.run_id, task.node_id)
        terminal_id = session.terminal_id

        try:
            # Wait for terminal init
            await self._wait_for_init(terminal_id)

            # Send task
            await self._send_task(terminal_id, task, input_artifacts)

            # Poll until done
            timeout_s = self.cao_config.timeout_minutes * 60.0
            await self._poll_until_done(terminal_id, timeout_s)

            # Fetch and parse output
            raw_output, possibly_truncated = await self._fetch_output(terminal_id)
            parsed_output = self._parse_output(raw_output)

        except Exception:
            # Cleanup on any error
            await self._cleanup_terminal(terminal_id)
            raise

        # Build artifacts
        input_ids = [a.id for a in input_artifacts]
        artifacts = self._build_artifacts(
            task.node_id, task.run_id, raw_output, parsed_output, input_ids,
            possibly_truncated=possibly_truncated,
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        provider = self.cao_config.provider or "claude_code"

        cost = CostRecord(
            id=f"cost_{uuid4().hex[:12]}",
            run_id=task.run_id,
            task_id=task.node_id,
            cost=0.0,
            source="subscription_based",
            model=f"cao/{provider}",
        )

        logger.info(
            "CAO Handoff complete: profile=%s terminal=%s elapsed=%dms",
            self.profile, terminal_id, elapsed_ms,
        )

        return ExecutionResult(artifacts=artifacts, cost=cost)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def cancel(self, task_id: str) -> None:
        """Cancel active CAO session (best-effort).

        *task_id* format is ``{run_id}_{node_id}``.  We look up the session
        by node_name first, then fall back to a suffix match.
        """
        session = self._active_sessions.get(task_id)
        if session is None:
            # Fallback: search by node_name suffix
            for _key, s in list(self._active_sessions.items()):
                if (
                    task_id == s.node_name
                    or task_id.endswith(f"_{s.node_name}")
                    or task_id.endswith(f".{s.node_name}")
                ):
                    session = s
                    break
        if session is None:
            return
        await self._cleanup_terminal(session.terminal_id)
        # Remove session record from SQLite (cleanup only marks completed)
        if self.session_store is not None:
            try:
                await self.session_store.delete_cao_session(session.terminal_id)
            except Exception:
                logger.debug("Failed to delete CAO session %s from store", session.terminal_id)

    async def _cleanup_terminal(self, terminal_id: str) -> None:
        """Best-effort exit + delete for a terminal."""
        try:
            client = await self._get_client()
            try:
                await client.post(f"/terminals/{terminal_id}/exit")
            except httpx.HTTPError:
                pass
            try:
                await client.delete(f"/terminals/{terminal_id}")
            except httpx.HTTPError:
                pass
        except httpx.HTTPError:
            logger.debug("Failed to cleanup terminal %s", terminal_id)

        if self.session_store is not None:
            try:
                await self.session_store.complete_cao_session(terminal_id)
            except Exception:
                logger.debug("Failed to complete CAO session %s in store", terminal_id)

        # Remove session by terminal_id
        self._active_sessions = {
            k: v for k, v in self._active_sessions.items()
            if v.terminal_id != terminal_id
        }

    async def close(self) -> None:
        """Clean up all active sessions and close HTTP client."""
        client = None
        if self._client is not None and not self._client.is_closed:
            client = self._client

        # Exit any still-active terminals
        for session in list(self._active_sessions.values()):
            if client:
                try:
                    await client.post(f"/terminals/{session.terminal_id}/exit")
                except httpx.HTTPError:
                    pass
            if self.session_store is not None:
                try:
                    await self.session_store.complete_cao_session(session.terminal_id)
                except Exception:
                    pass

        # Delete entire CAO sessions (removes session + all terminals at once)
        run_ids_to_clean = {s.run_id for s in self._active_sessions.values()}
        for run_id in run_ids_to_clean:
            session_name = self._run_sessions.get(run_id)
            if session_name and client:
                try:
                    await client.delete(f"/sessions/cao-{session_name}")
                except httpx.HTTPError:
                    logger.debug("Failed to delete CAO session cao-%s", session_name)

        # Clean up class-level state
        for run_id in run_ids_to_clean:
            self._run_sessions.pop(run_id, None)
            self._run_session_locks.pop(run_id, None)

        self._active_sessions.clear()

        # Close HTTP client
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
