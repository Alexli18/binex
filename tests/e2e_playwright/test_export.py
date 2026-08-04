"""E2E: Export page — run selection, format toggle, file download."""

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.parametrize("export_format", ["CSV", "JSON"])
def test_export_selected_runs(page: Page, export_format: str) -> None:
    page.goto("/export")
    expect(page.get_by_role("heading", name="Export Run Data")).to_be_visible()

    page.get_by_text("Select specific runs").click()
    page.get_by_role("checkbox", name=re.compile(r"^Select run ")).first.check()

    page.get_by_role("button", name=export_format, exact=True).click()

    with page.expect_download() as download_info:
        page.get_by_role("button", name=f"Download {export_format}").click()
    download = download_info.value

    assert download.suggested_filename == f"binex-export.{export_format.lower()}"
    assert download.path().stat().st_size > 0


@pytest.mark.xfail(
    reason="BUG #112: /api/v1/export has no last_n support — ExportRequest requires run_ids, "
    "frontend sends {last_n} in 'Last N runs' mode and gets 422",
    strict=True,
)
def test_export_last_n(page: Page) -> None:
    page.goto("/export")
    page.get_by_text("Last N runs").click()

    with page.expect_download(timeout=3_000) as download_info:
        page.get_by_role("button", name="Download JSON").click()

    assert download_info.value.path().stat().st_size > 0
