"""E2E: Cost Dashboard — KPI cards, charts, period selector (standalone page at /costs)."""
import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("period", ["24h", "7d", "30d", "all"])
def test_cost_dashboard(page: Page, period: str) -> None:
    """Test Cost Dashboard page for KPI cards, charts, and period selector."""
    page.goto("/costs")
    kpi_cards = ["Total Cost", "Avg per Run", "Total Runs", "Budget Used"]
    for card in kpi_cards:
        expect(page.get_by_text(card)).to_be_visible()
    period_select = page.get_by_label("Select period")
    expect(period_select).to_be_visible()
    period_select.click()
    # Radix Select renders its listbox in a portal at <body>, so search from page
    page.get_by_role("option", name=period, exact=True).click()
    expect(period_select).to_have_text(period)
    expect(page.get_by_text("Cost Trend")).to_be_visible()
    expect(page.get_by_text("Cost by Model")).to_be_visible()
    expect(page.get_by_text("Cost by Node")).to_be_visible()
