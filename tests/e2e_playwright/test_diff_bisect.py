"""E2E: Diff and Bisect pages — UI elements and interaction."""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.parametrize(
    "path, heading, select_a, select_b, compare_button, slider", [
            (
                "/diff", "Compare Runs", "diff-run-a-select", "diff-run-b-select",
                "diff-compare-btn", None
            ),
            (
                "/bisect", "Bisect", "bisect-good-run-select", "bisect-bad-run-select",
                "bisect-find-btn", "bisect-threshold-slider")
        ]
    )
def test_diff_bisect_pages(
    page: Page,
    path: str,
    heading: str,
    select_a: str,
    select_b: str,
    compare_button: str,
    slider: str | None
    ) -> None:
    page.goto(path)
    expect(page.get_by_role("heading", name=heading).first).to_be_visible()
    expect(page.get_by_test_id(select_a)).to_be_visible()
    expect(page.get_by_test_id(select_b)).to_be_visible()
    expect(page.get_by_test_id(compare_button)).to_be_disabled()
    if slider:
        expect(page.get_by_test_id(slider)).to_be_visible()
        expect(page.get_by_test_id(slider)).to_have_value("0.9")

