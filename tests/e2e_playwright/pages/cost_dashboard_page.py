from enum import Enum

from playwright.sync_api import Locator, Page

KPI_CARDS = ("Total Cost", "Avg per Run", "Total Runs", "Budget Used")
CHART_SECTIONS = ("Cost Trend", "Cost by Model", "Cost by Node")


class CostPeriod(Enum):
    H24 = "24h"
    D7 = "7d"
    D30 = "30d"
    ALL = "all"


class CostDashboardPage:
    """
    Represents the cost dashboard page (/costs) of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.period_select_locator = page.get_by_label("Select period")

    def goto(self) -> None:
        self.page.goto("/costs")

    def kpi_card(self, name: str) -> Locator:
        return self.page.get_by_text(name)

    def chart_section(self, name: str) -> Locator:
        return self.page.get_by_text(name)

    def select_period(self, period: CostPeriod) -> None:
        self.period_select_locator.click()
        # Radix Select renders its listbox in a portal at <body>, so search from page
        self.page.get_by_role("option", name=period.value, exact=True).click()
