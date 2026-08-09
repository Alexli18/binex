from playwright.sync_api import Page


class DiffPage:
    """
    Represents the run comparison (Compare Runs) page of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.heading_locator = page.get_by_role("heading", name="Compare Runs")
        self.run_a_select_locator = page.get_by_test_id("diff-run-a-select")
        self.run_b_select_locator = page.get_by_test_id("diff-run-b-select")
        self.compare_button_locator = page.get_by_test_id("diff-compare-btn")

    def goto(self) -> None:
        self.page.goto("/diff")
