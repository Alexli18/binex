"""E2E: Export page — run selection, format toggle, file download."""


import pytest
from playwright.sync_api import expect
from tests.e2e_playwright.pages.export_page import ExportFormat, ExportPage

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("export_format", [ExportFormat.CSV, ExportFormat.JSON])
def test_export_selected_runs(export_page: ExportPage, export_format: ExportFormat) -> None:
    export_page.goto()
    expect(export_page.heading_locator).to_be_visible()
    export_page.select_first_run()
    download = export_page.download(export_format)
    assert download.suggested_filename == f"binex-export.{export_format.name.lower()}"
    assert download.path().stat().st_size > 0


@pytest.mark.xfail(
    reason="BUG #112: /api/v1/export has no last_n support — ExportRequest requires run_ids, "
    "frontend sends {last_n} in 'Last N runs' mode and gets 422",
    strict=True,
)
def test_export_last_n(export_page: ExportPage) -> None:
    export_page.goto()
    export_page.select_export_mode_last_n(1)
    download = export_page.download(ExportFormat.JSON, timeout=3_000)
    assert download.path().stat().st_size > 0
