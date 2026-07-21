"""Re-export from standalone binex-trace package."""

from __future__ import annotations

import functools
import json
import sys
import time
from collections.abc import Callable
from typing import Any

try:
    from binex_trace import _TraceContext, trace
except ImportError:
    # Fallback: inline implementation for when binex-trace is not installed

    class _TraceContext:  # type: ignore[no-redef]
        """Thread-local trace state."""

        def __init__(self) -> None:
            self._stack: list[str] = []
            self._checkpoints: dict[str, Any] = {}

        def task(self, name: str) -> Callable[..., Any]:
            """Decorator to trace a function as a named task."""

            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                @functools.wraps(func)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    self._emit("task_start", name=name, args_repr=repr(args[:3]))
                    start = time.monotonic()
                    try:
                        result = func(*args, **kwargs)
                        elapsed = time.monotonic() - start
                        self._emit(
                            "task_end",
                            name=name,
                            status="ok",
                            duration_s=round(elapsed, 3),
                        )
                        return result
                    except Exception as e:
                        elapsed = time.monotonic() - start
                        self._emit(
                            "task_end",
                            name=name,
                            status="error",
                            error=str(e),
                            duration_s=round(elapsed, 3),
                        )
                        raise

                return wrapper

            return decorator

        def log(self, message: str, **kwargs: Any) -> None:
            """Emit a log event within the current task."""
            self._emit("log", message=message, **kwargs)

        def checkpoint(self, data: Any, label: str = "checkpoint") -> None:
            """Save a checkpoint (survives crash if stderr is captured)."""
            self._checkpoints[label] = data
            self._emit("checkpoint", label=label, data_preview=str(data)[:200])

        def progress(self, fraction: float, message: str = "") -> None:
            """Report progress on a long-running task (issue #78).

            ``fraction`` is 0..1; ``message`` is a short status like
            "transcribing 48/120 min". Keeps the node visibly alive so the
            heartbeat watchdog doesn't kill it.
            """
            self._emit(
                "progress",
                fraction=max(0.0, min(1.0, fraction)),
                message=message,
            )

        def _emit(self, event_type: str, **kwargs: Any) -> None:
            """Write structured JSON event to stderr."""
            event = {"_binex_trace": True, "type": event_type, "ts": time.time(), **kwargs}
            print(json.dumps(event, default=str), file=sys.stderr, flush=True)

    trace = _TraceContext()
