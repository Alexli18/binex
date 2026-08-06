"""Shared Base url fixture for Binex test suite."""

from __future__ import annotations

import pytest
from tests.e2e_playwright.pages.export_page import ExportPage
from tests.e2e_playwright.pages.sidebar import Sidebar


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the test server."""
    return "http://localhost:8420"

@pytest.fixture
def sidebar(page) -> Sidebar:
    return Sidebar(page)

@pytest.fixture
def export_page(page) -> ExportPage:
    return ExportPage(page)

TOUR_DISMISSED_STATE = {
    "cookies": [],
    "origins": [
        {
            "origin": "http://localhost:8420",
            "localStorage": [
                {"name": "binex.tour.v1.done", "value": "1"},
            ],
        }
    ],
}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    return {
        **browser_context_args,
        "storage_state": TOUR_DISMISSED_STATE,
    }
