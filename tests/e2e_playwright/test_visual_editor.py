"""E2E: Visual Editor — mode toggle, drag & drop, scaffold flow."""

import pytest
from playwright.sync_api import Page, expect
from tests.e2e_playwright.pages.editor_page import EditorMode, EditorPage, PaletteNode
from tests.e2e_playwright.pages.scaffold_page import ScaffoldPage

pytestmark = pytest.mark.e2e


def test_editor_mode_toggle_visual(page: Page, editor_page: EditorPage) -> None:
    """Test the Visual Editor mode toggle."""
    editor_page.goto()
    expect(editor_page.mode_button(EditorMode.VISUAL)).to_be_visible()
    expect(editor_page.mode_button(EditorMode.YAML)).to_be_visible()
    editor_page.switch_mode(EditorMode.VISUAL)
    for node in PaletteNode:
        expect(editor_page.palette_node(node)).to_be_visible()
    editor_page.switch_mode(EditorMode.YAML)
    expect(editor_page.monaco_locator).to_be_visible()

def test_editor_mode_toggle_yaml(page: Page, editor_page: EditorPage) -> None:
    """Test the YAML Editor mode toggle."""
    editor_page.goto()
    expect(editor_page.mode_button(EditorMode.VISUAL)).to_be_visible()
    expect(editor_page.mode_button(EditorMode.YAML)).to_be_visible()
    expect(editor_page.monaco_locator).to_be_visible()
    expect(editor_page.yaml_mode_editor_locator).to_be_visible()

def test_scaffold_to_editor_flow(
    page: Page, scaffold_page: ScaffoldPage, editor_page: EditorPage
) -> None:
    """Test the Scaffold → Editor flow."""
    scaffold_page.goto()
    expect(scaffold_page.dsl_input_locator).to_be_visible()
    scaffold_page.generate_from_dsl("A -> B -> C")
    expect(scaffold_page.open_editor_button_locator).to_be_visible()
    scaffold_page.open_in_editor()
    expect(page).to_have_url("/editor")
    expect(editor_page.monaco_locator).to_contain_text("nodes:")


def test_editor_save_as_modal(
    page: Page, scaffold_page: ScaffoldPage, editor_page: EditorPage
) -> None:
    """Test the Save As modal in the Visual Editor."""
    scaffold_page.goto()
    scaffold_page.generate_from_dsl("A -> B -> C")
    scaffold_page.open_in_editor()
    expect(page).to_have_url("/editor")
    expect(editor_page.save_button_locator).to_be_visible()
    save_modal = editor_page.open_save_as()
    expect(save_modal.modal_locator).to_be_visible()
    expect(save_modal.filename_input_locator).to_be_visible()
    expect(save_modal.cancel_button_locator).to_be_visible()
    save_modal.cancel()
    expect(save_modal.modal_locator).not_to_be_visible()
