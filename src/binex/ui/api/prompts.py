"""Human-in-the-loop prompt handling for Web UI.

Provides a PendingPrompts registry that Web human adapters use to wait
for browser responses, and a POST endpoint for submitting those responses.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["prompts"])


class PendingPrompts:
    """Registry for prompts awaiting human response via the Web UI."""

    def __init__(self) -> None:
        self._pending: dict[str, dict] = {}

    def register(self, prompt_id: str, metadata: dict | None = None) -> None:
        """Register a new pending prompt with an asyncio.Event."""
        self._pending[prompt_id] = {
            "event": asyncio.Event(),
            "response": None,
            "metadata": metadata or {},
        }

    async def wait(self, prompt_id: str, timeout: float | None = None) -> dict:
        """Block until the prompt receives a response.

        Returns the response dict. Raises TimeoutError if timeout exceeded.
        Raises KeyError if prompt_id not registered.
        """
        entry = self._pending.get(prompt_id)
        if entry is None:
            raise KeyError(f"Prompt '{prompt_id}' not registered")

        if timeout is not None:
            await asyncio.wait_for(entry["event"].wait(), timeout=timeout)
        else:
            await entry["event"].wait()

        response = entry["response"]
        # Clean up after retrieval
        del self._pending[prompt_id]
        return response

    def respond(self, prompt_id: str, data: dict) -> bool:
        """Submit a response for a pending prompt.

        Returns True if prompt existed and was resolved, False otherwise.
        """
        entry = self._pending.get(prompt_id)
        if entry is None:
            return False
        entry["response"] = data
        entry["event"].set()
        return True

    def is_pending(self, prompt_id: str) -> bool:
        """Check if a prompt is still waiting for a response."""
        entry = self._pending.get(prompt_id)
        return entry is not None and not entry["event"].is_set()

    def list_pending(self, run_id: str | None = None) -> list[dict]:
        """List all pending prompts, optionally filtered by run_id."""
        results = []
        for pid, entry in self._pending.items():
            if entry["event"].is_set():
                continue
            meta = entry["metadata"]
            if run_id is not None and meta.get("run_id") != run_id:
                continue
            results.append({"prompt_id": pid, **meta})
        return results


pending_prompts = PendingPrompts()  # module-level singleton


class RespondRequest(BaseModel):
    """Request body for submitting a human response."""

    prompt_id: str
    action: str  # "approve", "reject", "input"
    text: str = ""


@router.post("/{run_id}/respond")
async def respond_to_prompt(run_id: str, body: RespondRequest) -> JSONResponse:
    """Submit a human response for a pending prompt."""
    if not pending_prompts.is_pending(body.prompt_id):
        return JSONResponse(
            {"error": f"Prompt '{body.prompt_id}' not found or already answered"},
            status_code=404,
        )

    pending_prompts.respond(
        body.prompt_id,
        {"action": body.action, "text": body.text},
    )
    logger.info("Prompt %s responded: action=%s", body.prompt_id, body.action)
    return JSONResponse({"status": "ok", "prompt_id": body.prompt_id})


@router.get("/{run_id}/prompts")
async def list_prompts(run_id: str) -> JSONResponse:
    """List pending prompts for a run."""
    prompts = pending_prompts.list_pending(run_id=run_id)
    return JSONResponse({"prompts": prompts})
