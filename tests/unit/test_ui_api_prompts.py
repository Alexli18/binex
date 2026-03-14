"""Tests for the prompts API endpoint."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from binex.ui.api.prompts import PendingPrompts, pending_prompts
from binex.ui.server import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestPendingPrompts:
    def test_register_and_is_pending(self):
        pp = PendingPrompts()
        pp.register("p1")
        assert pp.is_pending("p1") is True
        assert pp.is_pending("unknown") is False

    def test_respond_returns_true(self):
        pp = PendingPrompts()
        pp.register("p1")
        assert pp.respond("p1", {"action": "approve"}) is True

    def test_respond_unknown_returns_false(self):
        pp = PendingPrompts()
        assert pp.respond("unknown", {"action": "approve"}) is False

    @pytest.mark.asyncio
    async def test_wait_returns_response(self):
        pp = PendingPrompts()
        pp.register("p1")

        async def do_respond():
            await asyncio.sleep(0.01)
            pp.respond("p1", {"action": "approve", "text": ""})

        asyncio.create_task(do_respond())
        result = await pp.wait("p1")
        assert result == {"action": "approve", "text": ""}

    @pytest.mark.asyncio
    async def test_wait_cleans_up(self):
        pp = PendingPrompts()
        pp.register("p1")
        pp.respond("p1", {"action": "input", "text": "hello"})
        await pp.wait("p1")
        assert pp.is_pending("p1") is False

    @pytest.mark.asyncio
    async def test_wait_timeout(self):
        pp = PendingPrompts()
        pp.register("p1")
        with pytest.raises(asyncio.TimeoutError):
            await pp.wait("p1", timeout=0.01)

    @pytest.mark.asyncio
    async def test_wait_unknown_raises_key_error(self):
        pp = PendingPrompts()
        with pytest.raises(KeyError):
            await pp.wait("unknown")

    def test_list_pending(self):
        pp = PendingPrompts()
        pp.register("p1", metadata={"run_id": "run-1", "node_id": "n1"})
        pp.register("p2", metadata={"run_id": "run-2", "node_id": "n2"})
        pp.register("p3", metadata={"run_id": "run-1", "node_id": "n3"})

        all_pending = pp.list_pending()
        assert len(all_pending) == 3

        run1 = pp.list_pending(run_id="run-1")
        assert len(run1) == 2
        assert {p["prompt_id"] for p in run1} == {"p1", "p3"}

    def test_list_pending_excludes_answered(self):
        pp = PendingPrompts()
        pp.register("p1", metadata={"run_id": "run-1"})
        pp.register("p2", metadata={"run_id": "run-1"})
        pp.respond("p1", {"action": "approve"})

        pending = pp.list_pending(run_id="run-1")
        assert len(pending) == 1
        assert pending[0]["prompt_id"] == "p2"


class TestRespondEndpoint:
    @pytest.mark.asyncio
    async def test_respond_success(self, client):
        pending_prompts.register("p-test", metadata={"run_id": "run-1"})

        resp = await client.post(
            "/api/v1/runs/run-1/respond",
            json={"prompt_id": "p-test", "action": "approve", "text": ""},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["prompt_id"] == "p-test"

    @pytest.mark.asyncio
    async def test_respond_not_found(self, client):
        resp = await client.post(
            "/api/v1/runs/run-1/respond",
            json={"prompt_id": "nonexistent", "action": "approve", "text": ""},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_respond_already_answered(self, client):
        pending_prompts.register("p-dup", metadata={"run_id": "run-1"})
        pending_prompts.respond("p-dup", {"action": "approve"})

        resp = await client.post(
            "/api/v1/runs/run-1/respond",
            json={"prompt_id": "p-dup", "action": "approve", "text": ""},
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_prompts(self, client):
        pending_prompts.register("p-list-1", metadata={"run_id": "run-list"})
        pending_prompts.register("p-list-2", metadata={"run_id": "run-list"})

        resp = await client.get("/api/v1/runs/run-list/prompts")

        assert resp.status_code == 200
        data = resp.json()
        assert "prompts" in data
        prompt_ids = {p["prompt_id"] for p in data["prompts"]}
        assert "p-list-1" in prompt_ids
        assert "p-list-2" in prompt_ids

    @pytest.mark.asyncio
    async def test_list_prompts_empty(self, client):
        resp = await client.get("/api/v1/runs/run-empty/prompts")

        assert resp.status_code == 200
        assert resp.json() == {"prompts": []}
