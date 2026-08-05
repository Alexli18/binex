"""Shared Base url fixture for Binex test suite."""

from __future__ import annotations

import pytest
from tests.e2e_playwright.pages.sidebar import Sidebar


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the test server."""
    return "http://localhost:8420"

@pytest.fixture
def sidebar(page) -> Sidebar:
    return Sidebar(page)
