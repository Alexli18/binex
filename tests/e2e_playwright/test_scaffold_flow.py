"""E2E: Scaffold wizard — DSL generation and template selection."""

import pytest
import yaml
from playwright.sync_api import Page, expect


def test_scaffold_flow_dsl(page: Page) -> None:
    page.goto("/scaffold")
    expect(page.get_by_role("heading", name="Create Workflow").first).to_be_visible()
    dsl_input = page.get_by_test_id("scaffold-dsl-input")
    dsl_input.fill("A -> B -> C")
    generate_btn = page.get_by_test_id("scaffold-generate-btn")
    generate_btn.click()
    yaml_output = page.get_by_test_id("scaffold-yaml-output")
    expect(yaml_output).to_be_visible()
    expect(yaml_output).to_contain_text("nodes:")
    yaml_content = yaml_output.inner_text()
    try:
        parsed_data = yaml.safe_load(yaml_content)
        assert isinstance(parsed_data, (dict, list))
        nodes = parsed_data.get("nodes", {})
        assert isinstance(nodes, dict)
        for node_name in ["A", "B", "C"]:
            assert node_name in nodes, f"Node '{node_name}' not found in generated YAML"
    except yaml.YAMLError as e:
        pytest.fail(f"Failed to parse YAML: {e}")

def test_scaffold_flow_template(page: Page) -> None:
    page.goto("/scaffold")
    expect(page.get_by_role("heading", name="Create Workflow").first).to_be_visible()
    template_tab = page.get_by_test_id("scaffold-tab-template")
    template_tab.click()
    pattern_cards = page.locator('[data-testid^="scaffold-pattern-"]')
    expect(pattern_cards).to_have_count(25)

def test_scaffold_flow_blank(page: Page) -> None:
    page.goto("/scaffold")
    expect(page.get_by_role("heading", name="Create Workflow").first).to_be_visible()
    blank_tab = page.get_by_test_id("scaffold-tab-blank")
    blank_tab.click()
    open_editor_btn = page.get_by_test_id("scaffold-blank-open-editor-btn")
    expect(open_editor_btn).to_be_visible()
