"""SSE event streaming for Binex Web UI."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/runs", tags=["events"])


class EventBus:
    """Pub/sub event bus for real-time run events."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Create a new subscription queue for a run."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscription queue."""
        if run_id in self._subscribers:
            self._subscribers[run_id] = [
                q for q in self._subscribers[run_id] if q is not queue
            ]

    async def publish(self, run_id: str, event: dict) -> None:
        """Publish an event to all subscribers of a run."""
        for queue in self._subscribers.get(run_id, []):
            await queue.put(event)


event_bus = EventBus()  # module-level singleton


@router.get("/{run_id}/events")
async def stream_events(run_id: str) -> StreamingResponse:
    """Stream SSE events for a workflow run."""
    queue = event_bus.subscribe(run_id)

    async def generate():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                except TimeoutError:
                    # Send keepalive comment to detect broken connections
                    yield ": keepalive\n\n"
                    continue
                except asyncio.CancelledError:
                    break
                event_type = event.get("type", "message")
                data = json.dumps(event)
                yield f"event: {event_type}\ndata: {data}\n\n"
                if event_type in ("run:completed", "run:cancelled"):
                    break
        finally:
            event_bus.unsubscribe(run_id, queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
