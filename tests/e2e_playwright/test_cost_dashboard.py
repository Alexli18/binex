"""E2E: Cost Dashboard — KPI cards, charts, period selector (standalone page at /costs)."""
import pytest
from playwright.sync_api import Page, expect
from tests.e2e_playwright.pages.cost_dashboard_page import (
    CHART_SECTIONS,
    KPI_CARDS,
    CostDashboardPage,
    CostPeriod,
)

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize("period", list(CostPeriod))
def test_cost_dashboard(
    page: Page, cost_dashboard_page: CostDashboardPage, period: CostPeriod
) -> None:
    """Test Cost Dashboard page for KPI cards, charts, and period selector."""
    cost_dashboard_page.goto()
    for card in KPI_CARDS:
        expect(cost_dashboard_page.kpi_card(card)).to_be_visible()
    expect(cost_dashboard_page.period_select_locator).to_be_visible()
    cost_dashboard_page.select_period(period)
    expect(cost_dashboard_page.period_select_locator).to_have_text(period.value)
    for section in CHART_SECTIONS:
        expect(cost_dashboard_page.chart_section(section)).to_be_visible()
