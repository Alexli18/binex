from enum import Enum

from playwright.sync_api import Locator, Page


class EditorMode(Enum):
    VISUAL = "visual"
    YAML = "yaml"


class PaletteNode(Enum):
    LLM = "llm"
    LOCAL = "local"
    HUMAN_APPROVE = "human-approve"
    HUMAN_INPUT = "human-input"
    A2A = "a2a"


class SaveAsModal:
    """
    Represents the Save As modal opened from the editor toolbar.
    """

    def __init__(self, page: Page):
        self.page = page
        self.modal_locator = page.get_by_test_id("save-as-modal")
        self.filename_input_locator = page.get_by_test_id("save-as-filename-input")
        self.cancel_button_locator = page.get_by_test_id("save-as-cancel-btn")

    def cancel(self) -> None:
        self.cancel_button_locator.click()


class EditorPage:
    """
    Represents the visual/YAML workflow editor page of the application.
    """

    def __init__(self, page: Page):
        """
        Args:
            page (Page): The Playwright Page instance.
        """
        self.page = page
        self.monaco_locator = page.locator(".monaco-editor")
        self.yaml_mode_editor_locator = page.locator("[data-mode-id='yaml']")
        self.save_button_locator = page.get_by_test_id("editor-save-btn")

    def goto(self) -> None:
        self.page.goto("/editor")

    def mode_button(self, mode: EditorMode) -> Locator:
        return self.page.get_by_test_id(f"editor-mode-{mode.value}")

    def switch_mode(self, mode: EditorMode) -> None:
        self.mode_button(mode).click()

    def palette_node(self, node: PaletteNode) -> Locator:
        return self.page.get_by_test_id(f"palette-node-{node.value}")

    def open_save_as(self) -> SaveAsModal:
        self.save_button_locator.click()
        return SaveAsModal(self.page)
