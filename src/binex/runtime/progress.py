"""Progress reporting and heartbeat timeouts for long-running nodes.

An LLM node streams tokens, so it's visibly alive. A ``local://`` node running
Whisper on a two-hour audio track is silent for thirty minutes — and the default
deadline kills it. A node that *reports progress* is alive; the timeout should
apply to silence, not total duration. See issue #78.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any


class ProgressReporter:
    """Handed to a node's handler as ``report_progress(fraction, message)``.

    Each call refreshes the heartbeat (so the watchdog knows the node is alive)
    and forwards a progress event to the runtime for the UI / trace.
    """

    def __init__(
        self,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> None:
        self._on_progress = on_progress
        self.last_beat: float = self._now()

    @staticmethod
    def _now() -> float:
        try:
            return asyncio.get_event_loop().time()
        except RuntimeError:
            return 0.0

    def report(self, fraction: float, message: str = "") -> None:
        """Report progress: fraction in [0, 1] plus an optional status message."""
        self.last_beat = self._now()
        if self._on_progress is not None:
            self._on_progress(max(0.0, min(1.0, fraction)), message)


class HeartbeatTimeoutError(TimeoutError):
    """Raised when a node produces no progress within its heartbeat window."""


async def run_with_heartbeat(
    coro: asyncio.Future[Any] | asyncio.Task[Any],
    reporter: ProgressReporter,
    *,
    heartbeat_timeout_s: float,
    deadline_s: float | None = None,
) -> Any:
    """Await ``coro``, cancelling it if it goes silent for too long.

    The node is considered hung when no progress has been reported for
    ``heartbeat_timeout_s``. ``deadline_s`` is an optional hard total-duration
    cap that still applies.
    """
    task = asyncio.ensure_future(coro)
    loop = asyncio.get_event_loop()
    deadline = (loop.time() + deadline_s) if deadline_s else None

    while True:
        try:
            return await asyncio.wait_for(
                asyncio.shield(task), timeout=heartbeat_timeout_s,
            )
        except TimeoutError:
            idle = loop.time() - reporter.last_beat
            if idle >= heartbeat_timeout_s:
                task.cancel()
                raise HeartbeatTimeoutError(
                    f"no progress for {heartbeat_timeout_s:.0f}s"
                ) from None
            if deadline is not None and loop.time() >= deadline:
                task.cancel()
                raise TimeoutError("deadline exceeded") from None
            # A recent heartbeat kept it alive — keep waiting.
