"""E2E: Sidebar navigation — all pages reachable and render correctly."""

import re

import pytest
from playwright.sync_api import Page, expect


def test_sidebar_renders(page: Page) -> None:
    page.goto("/")
    expect(page.locator("aside")).to_be_visible()


@pytest.mark.parametrize("group", ["Build", "Runs", "Analyze", "System"])
def test_sidebar_group_visible(page: Page, group: str) -> None:
    page.goto("/")
    expect(page.get_by_text(group, exact=True).first).to_be_visible()


@pytest.mark.parametrize(
    "link_text, expected_path, expected_heading",
    [
        ("Editor", "/editor", None),  # страница редактора без заголовка — только тулбар
        ("Scaffold", "/scaffold", "Create Workflow"),
        ("Prompts", "/prompts", "Prompt"),
        ("Dashboard", "/", "Dashboard"),
        ("Compare", "/diff", "Compare"),
        ("Bisect", "/bisect", "Bisect"),
        ("Doctor", "/system/doctor", "System Health"),
        ("Plugins", "/system/plugins", "Plugins"),
        ("Gateway", "/system/gateway", "A2A Gateway"),
    ],
)
def test_sidebar_navigation(
    page: Page, 
    link_text: str, 
    expected_path: str, 
    expected_heading: str
    ) -> None:
    page.goto("/")
    page.get_by_role("link", name=link_text, exact=True).first.click()
    expect(page).to_have_url(re.compile(f".*{re.escape(expected_path)}.*"))
    if expected_heading is not None:
        expect(page.get_by_role("heading", name=expected_heading).first).to_be_visible()


def test_sidebar_collapse_expand(page: Page) -> None:
    page.goto("/")
    sidebar = page.locator("aside")
    expect(sidebar).to_have_attribute("style", re.compile(r"width:\s*200px"))

    collapse_btn = sidebar.locator("button").first
    collapse_btn.click()
    expect(sidebar).to_have_attribute("style", re.compile(r"width:\s*40px"))

    collapse_btn.click()
    expect(sidebar).to_have_attribute("style", re.compile(r"width:\s*200px"))


def test_active_nav_state(page: Page) -> None:
    page.goto("/editor")
    active_link = page.locator("a[aria-current='page']")
    expect(active_link).to_have_count(1)
