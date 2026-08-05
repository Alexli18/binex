"""E2E: Visual Editor — mode toggle, drag & drop, scaffold flow."""

from playwright.sync_api import Page, expect


def test_editor_mode_toggle_visual(page: Page) -> None:
    """Test the Visual Editor mode toggle."""
    page.goto("/editor")
    visual_btn = page.get_by_test_id("editor-mode-visual")
    yaml_btn = page.get_by_test_id("editor-mode-yaml")
    expect(visual_btn).to_be_visible()
    expect(yaml_btn).to_be_visible()
    visual_btn.click()
    expect(page.get_by_test_id("palette-node-llm")).to_be_visible()
    expect(page.get_by_test_id("palette-node-local")).to_be_visible()
    expect(page.get_by_test_id("palette-node-human-approve")).to_be_visible()
    expect(page.get_by_test_id("palette-node-human-input")).to_be_visible()
    expect(page.get_by_test_id("palette-node-a2a")).to_be_visible()
    yaml_btn.click()
    expect(page.locator(".monaco-editor")).to_be_visible()

def test_editor_mode_toggle_yaml(page: Page) -> None:
    """Test the YAML Editor mode toggle."""
    page.goto("/editor")
    visual_btn = page.get_by_test_id("editor-mode-visual")
    yaml_btn = page.get_by_test_id("editor-mode-yaml")
    expect(visual_btn).to_be_visible()
    expect(yaml_btn).to_be_visible()
    expect(page.locator(".monaco-editor")).to_be_visible()
    editor_yaml = page.locator("[data-mode-id='yaml']")
    expect(editor_yaml).to_be_visible()

def test_scaffold_to_editor_flow(page: Page) -> None:
    """Test the Scaffold → Editor flow."""
    page.goto("/scaffold")
    dsl_input = page.get_by_test_id("scaffold-dsl-input")
    expect(dsl_input).to_be_visible()
    dsl_input.fill("A -> B -> C")
    generate_btn = page.get_by_test_id("scaffold-generate-btn")
    expect(generate_btn).to_be_visible()
    generate_btn.click()
    open_editor_btn = page.get_by_test_id("scaffold-open-editor-btn")
    expect(open_editor_btn).to_be_visible()
    open_editor_btn.click()
    expect(page).to_have_url("/editor")
    expect(page.locator(".monaco-editor")).to_contain_text("nodes:")


def test_editor_save_as_modal(page: Page) -> None:
    """Test the Save As modal in the Visual Editor."""
    page.goto("/scaffold")
    dsl_input = page.get_by_test_id("scaffold-dsl-input")
    dsl_input.fill("A -> B -> C")
    generate_btn = page.get_by_test_id("scaffold-generate-btn")
    generate_btn.click()
    open_editor_btn = page.get_by_test_id("scaffold-open-editor-btn")
    open_editor_btn.click()
    expect(page).to_have_url("/editor")
    save_btn = page.get_by_test_id("editor-save-btn")
    expect(save_btn).to_be_visible()
    save_btn.click()
    save_modal = page.get_by_test_id("save-as-modal")
    expect(save_modal).to_be_visible()
    filename_input = page.get_by_test_id("save-as-filename-input")
    expect(filename_input).to_be_visible()
    cancel_btn = page.get_by_test_id("save-as-cancel-btn")
    expect(cancel_btn).to_be_visible()
    cancel_btn.click()
    expect(save_modal).not_to_be_visible()
