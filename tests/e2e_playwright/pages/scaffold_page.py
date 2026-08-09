from enum import Enum

from playwright.sync_api import Locator, Page


class ScaffoldTab(Enum):
    TEMPLATE = "template"
    BLANK = "blank"


class ScaffoldPage:
    """
    Represents the scaffold (Create Workflow) page of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.heading_locator = page.get_by_role("heading", name="Create Workflow")
        self.dsl_input_locator = page.get_by_test_id("scaffold-dsl-input")
        self.generate_button_locator = page.get_by_test_id("scaffold-generate-btn")
        self.yaml_output_locator = page.get_by_test_id("scaffold-yaml-output")
        self.pattern_cards_locator = page.locator('[data-testid^="scaffold-pattern-"]')
        self.open_editor_button_locator = page.get_by_test_id("scaffold-open-editor-btn")
        self.blank_open_editor_button_locator = page.get_by_test_id(
            "scaffold-blank-open-editor-btn"
        )

    def goto(self) -> None:
        self.page.goto("/scaffold")

    def tab(self, tab: ScaffoldTab) -> Locator:
        return self.page.get_by_test_id(f"scaffold-tab-{tab.value}")

    def open_tab(self, tab: ScaffoldTab) -> None:
        self.tab(tab).click()

    def generate_from_dsl(self, dsl: str) -> None:
        """Fill the DSL input and click Generate."""
        self.dsl_input_locator.fill(dsl)
        self.generate_button_locator.click()

    def yaml_text(self) -> str:
        return self.yaml_output_locator.inner_text()

    def open_in_editor(self) -> None:
        self.open_editor_button_locator.click()
