"""Re-export from standalone binex-trace package."""

try:
    from binex_trace import trace, _TraceContext
except ImportError:
    # Fallback: inline implementation for when binex-trace is not installed
    import functools
    import json
    import sys
    import time
    from typing import Any

    class _TraceContext:
        """Thread-local trace state."""

        def __init__(self) -> None:
            self._stack: list[str] = []
            self._checkpoints: dict[str, Any] = {}

        def task(self, name: str):  # type: ignore[type-arg]
            """Decorator to trace a function as a named task."""

            def decorator(func):  # type: ignore[type-arg]
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

        def _emit(self, event_type: str, **kwargs: Any) -> None:
            """Write structured JSON event to stderr."""
            event = {"_binex_trace": True, "type": event_type, "ts": time.time(), **kwargs}
            print(json.dumps(event, default=str), file=sys.stderr, flush=True)

    trace = _TraceContext()
