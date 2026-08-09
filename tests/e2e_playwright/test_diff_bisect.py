"""E2E: Diff and Bisect pages — UI elements and interaction."""
import pytest
from playwright.sync_api import Page, expect
from tests.e2e_playwright.pages.bisect_page import BisectPage
from tests.e2e_playwright.pages.diff_page import DiffPage

pytestmark = pytest.mark.e2e


def test_diff_page(page: Page, diff_page: DiffPage) -> None:
    diff_page.goto()
    expect(diff_page.heading_locator.first).to_be_visible()
    expect(diff_page.run_a_select_locator).to_be_visible()
    expect(diff_page.run_b_select_locator).to_be_visible()
    expect(diff_page.compare_button_locator).to_be_disabled()


def test_bisect_page(page: Page, bisect_page: BisectPage) -> None:
    bisect_page.goto()
    expect(bisect_page.heading_locator.first).to_be_visible()
    expect(bisect_page.good_run_select_locator).to_be_visible()
    expect(bisect_page.bad_run_select_locator).to_be_visible()
    expect(bisect_page.find_button_locator).to_be_disabled()
    expect(bisect_page.threshold_slider_locator).to_be_visible()
    expect(bisect_page.threshold_slider_locator).to_have_value("0.9")
