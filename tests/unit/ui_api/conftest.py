"""Shared fixtures for Web UI API tests.

Every test in this package talks to the FastAPI app through
httpx.ASGITransport; the canonical ``app``/``client``/``stores`` trio
lives here. A test file may still define its own fixture with the same
name to override locally.
"""

from __future__ import annotations

import httpx
import pytest

from binex.stores.backends.memory import InMemoryArtifactStore, InMemoryExecutionStore
from binex.ui.server import create_app


@pytest.fixture
def stores():
    exec_store = InMemoryExecutionStore()
    art_store = InMemoryArtifactStore()
    return exec_store, art_store


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
