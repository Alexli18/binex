from enum import Enum

from playwright.sync_api import Locator, Page


class SidebarGroup(Enum):
    """
    Enum representing the sidebar groups.
    """
    BUILD = "Build"
    RUNS = "Runs"
    ANALYZE = "Analyze"
    SYSTEM = "System"

class SidebarLink(Enum):
    """
    Enum representing the sidebar links.
    """
    EDITOR = "Editor"
    SCAFFOLD = "Scaffold"
    PROMPTS = "Prompts"
    DASHBOARD = "Dashboard"
    COMPARE = "Compare"
    COSTS = "Costs"
    BISECT = "Bisect"
    SCHEDULER = "Scheduler"
    GATEWAY = "Gateway"
    PLUGINS = "Plugins"
    DOCTOR = "Doctor"

class Sidebar:
    """
    Represents the sidebar component of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.sidebar_locator = page.locator("aside")
        self.collapse_button_locator = self.sidebar_locator.get_by_test_id("sidebar-collapse")

    def link(self, name: SidebarLink) -> Locator:
        return self.sidebar_locator.get_by_test_id(f"sidebar-link-{name.value.lower()}")

    def group(self, name: SidebarGroup) -> Locator:
        return self.sidebar_locator.get_by_test_id(f"sidebar-group-{name.value.lower()}")

    def navigate_to(self, link_name: SidebarLink):
        """
        Clicks a sidebar link based on the provided link name.

        Args:
            link_name (SidebarLink): The name of the sidebar link to click.
        """
        link_locator = self.link(link_name)
        link_locator.click()

    def collapse(self):
        """
        Collapses the sidebar.
        """
        self.collapse_button_locator.click()

