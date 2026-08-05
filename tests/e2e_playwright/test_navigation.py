"""E2E: Sidebar navigation — all pages reachable and render correctly."""

import re

import pytest
from playwright.sync_api import Page, expect
from tests.e2e_playwright.pages.sidebar import Sidebar, SidebarGroup, SidebarLink

pytestmark = pytest.mark.e2e


def test_sidebar_renders(page: Page, sidebar: Sidebar) -> None:
    page.goto("/")
    expect(sidebar.sidebar_locator).to_be_visible()


@pytest.mark.parametrize(
    "group",
    [SidebarGroup.BUILD, SidebarGroup.RUNS, SidebarGroup.ANALYZE, SidebarGroup.SYSTEM]
    )
def test_sidebar_group_visible(page: Page, sidebar: Sidebar, group: SidebarGroup) -> None:
    page.goto("/")
    expect(sidebar.group(group)).to_be_visible()


@pytest.mark.parametrize(
    "link_text, expected_path, expected_heading",
    [
        (SidebarLink.EDITOR, "/editor", None),  # editor page has no heading
        (SidebarLink.SCAFFOLD, "/scaffold", "Create Workflow"),
        (SidebarLink.PROMPTS, "/prompts", "Prompt"),
        (SidebarLink.DASHBOARD, "/", "Dashboard"),
        (SidebarLink.COMPARE, "/diff", "Compare"),
        (SidebarLink.BISECT, "/bisect", "Bisect"),
        (SidebarLink.DOCTOR, "/system/doctor", "System Health"),
        (SidebarLink.PLUGINS, "/system/plugins", "Plugins"),
        (SidebarLink.GATEWAY, "/system/gateway", "A2A Gateway"),
    ],
)
def test_sidebar_navigation(
    page: Page,
    sidebar: Sidebar,
    link_text: SidebarLink,
    expected_path: str,
    expected_heading: str
    ) -> None:
    page.goto("/")
    sidebar.link(link_text).click()
    expect(page).to_have_url(re.compile(f".*{re.escape(expected_path)}.*"))
    if expected_heading is not None:
        expect(page.get_by_role("heading", name=expected_heading).first).to_be_visible()


def test_sidebar_collapse_expand(page: Page, sidebar: Sidebar) -> None:
    page.goto("/")
    expect(sidebar.sidebar_locator).to_have_attribute("style", re.compile(r"width:\s*200px"))

    sidebar.collapse()
    expect(sidebar.sidebar_locator).to_have_attribute("style", re.compile(r"width:\s*40px"))

    sidebar.collapse()
    expect(sidebar.sidebar_locator).to_have_attribute("style", re.compile(r"width:\s*200px"))


def test_active_nav_state(page: Page) -> None:
    page.goto("/editor")
    active_link = page.locator("a[aria-current='page']")
    expect(active_link).to_have_count(1)

