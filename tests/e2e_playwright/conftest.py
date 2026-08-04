"""Shared Base url fixture for Binex test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the test server."""
    return "http://localhost:8420"
