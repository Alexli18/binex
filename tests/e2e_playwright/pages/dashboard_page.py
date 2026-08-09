from playwright.sync_api import Locator, Page


class DashboardPage:
    """
    Represents the runs dashboard (home) page of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.run_links_locator = page.locator('[data-testid^="dashboard-run-link-run_"]')

    def goto(self) -> None:
        self.page.goto("/")

    def first_run_link(self) -> Locator:
        return self.run_links_locator.first

    def run_link(self, run_id: str) -> Locator:
        return self.page.get_by_test_id(f"dashboard-run-link-{run_id}")
