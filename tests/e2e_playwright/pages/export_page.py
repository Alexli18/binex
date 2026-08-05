from enum import Enum

from playwright.sync_api import Download, Page


class ExportFormat(Enum):
    CSV = "CSV"
    JSON = "JSON"

class ExportPage:
    """
    Represents the export page of the application.
    """
    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.heading_locator = page.get_by_role("heading", name="Export Run Data")
        self.specific_run_locator = page.get_by_test_id("export-mode-select-runs")
        self.export_mode_last_n_locator = page.get_by_test_id("export-mode-last-n")
        self.select_all_runs_locator = page.get_by_test_id("export-select-all")
        self.export_include_artifacts_locator = page.get_by_test_id("export-include-artifacts")
        self.export_download_button_locator = page.get_by_test_id("export-download")
        self.export_last_n_input_locator = page.get_by_test_id("export-last-n-input")

    def select_first_run(self):
        self.specific_run_locator.check()
        self.page.locator('[data-testid^="export-run-checkbox-"]').first.check()

    def download(self, fmt: ExportFormat, timeout: float = 30_000) -> Download:
        self.select_format(fmt)
        with self.page.expect_download(timeout=timeout) as info:
            self.export_download_button_locator.click()
        return info.value

    def goto(self) -> None:
        self.page.goto("/export")

    def select_export_mode_last_n(self, n: int):
        self.export_mode_last_n_locator.check()
        self.export_last_n_input_locator.fill(str(n))

    def select_run_by_id(self, run_id: str):
        self.specific_run_locator.check()
        self.page.get_by_test_id(f"export-run-checkbox-{run_id}").check()

    def select_format(self, fmt: ExportFormat) -> None:
        self.page.get_by_test_id(f"export-format-{fmt.value.lower()}").click()

    def checkbox_include_artifacts(self, check: bool) -> None:
        if check:
            self.export_include_artifacts_locator.check()
        else:
            self.export_include_artifacts_locator.uncheck()



