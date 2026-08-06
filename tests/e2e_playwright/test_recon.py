"""Reconnaissance: screenshot all pages to verify they load."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

PAGES = [
    ("/", "Dashboard"),
    ("/editor", None), # editor page has no heading, only toolbar
    ("/scaffold", "Create Workflow"),
    ("/diff", "Compare Runs"),
    ("/bisect", "Bisect — Find Divergence"),
    ("/costs", "Cost Dashboard"),
    ("/prompts", "Prompt Library"),
    ("/scheduler", "Scheduler"),
    ("/export", "Export Run Data"),
    ("/system/doctor", "System Health"),
    ("/system/plugins", "Plugins & Adapters"),
    ("/system/gateway", "A2A Gateway"),
    ("/asadss", "Page Not Found"),
]


@pytest.mark.parametrize("path, heading", PAGES)
def test_page_loads(page: Page, path: str, heading: str) -> None:
    """Check that each page loads and has a heading."""
    page.goto(path)
    expect(page).to_have_url(path)
    # Check page has content (not blank)
    main = page.locator("main").first
    expect(main).to_be_visible()
    expect(main).not_to_be_empty()
    if heading is not None:
        expect(page.get_by_role("heading", name=heading).first).to_be_visible()
    else:
        expect(page.get_by_role("heading", name="Page Not Found")).to_have_count(0)
