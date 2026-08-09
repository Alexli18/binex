from playwright.sync_api import Page


class BisectPage:
    """
    Represents the bisect (first-divergence search) page of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.heading_locator = page.get_by_role("heading", name="Bisect")
        self.good_run_select_locator = page.get_by_test_id("bisect-good-run-select")
        self.bad_run_select_locator = page.get_by_test_id("bisect-bad-run-select")
        self.find_button_locator = page.get_by_test_id("bisect-find-btn")
        self.threshold_slider_locator = page.get_by_test_id("bisect-threshold-slider")

    def goto(self) -> None:
        self.page.goto("/bisect")
