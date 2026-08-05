"""E2E: Scaffold wizard — DSL generation and template selection."""

from playwright.sync_api import Page, expect


def test_scaffold_flow(page: Page) -> None:
    """Test the scaffold flow: DSL generation, template selection, and blank mode."""
    page.goto("/scaffold", wait_until="networkidle")

    # Check that the Scaffold page loads
    expect(page.get_by_role("heading", name="Create Workflow")).to_be_visible()

    # Check that the DSL tab is active
    expect(page.get_by_test_id("scaffold-tab-dsl")).to_be_enabled()

    # Type a DSL expression
    dsl_input = page.get_by_test_id("scaffold-dsl-input")
    dsl_input.fill("A -> B -> C")
    expect(dsl_input).to_have_value("A -> B -> C")

    # Click the Generate button
    generate_btn = page.get_by_role("button", name="Generate")
    generate_btn.click()

    # Check that YAML was generated
    yaml_output = page.get_by_test_id("scaffold-yaml-output")
    expect(yaml_output).to_be_visible()

    # Switch to Template mode
    template_tab = page.get_by_test_id("scaffold-tab-template")
    template_tab.click()
    expect(template_tab).to_be_enabled()
    # Check that pattern cards are visible
    pattern_cards = page.locator('[data-testid^="scaffold-pattern-"]')
    expect(pattern_cards).to_have_count(25)

    # Switch to Blank mode
    blank_tab = page.get_by_test_id("scaffold-tab-blank")
    blank_tab.click()
    expect(blank_tab).to_be_enabled()
    expect(page.get_by_test_id("scaffold-blank-open-editor-btn")).to_be_visible()
    expect(page.get_by_test_id("scaffold-blank-open-editor-btn")).to_be_enabled()
