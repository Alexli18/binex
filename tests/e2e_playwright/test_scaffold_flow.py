"""E2E: Scaffold wizard — DSL generation and template selection."""

import pytest
import yaml
from playwright.sync_api import Page, expect
from tests.e2e_playwright.pages.scaffold_page import ScaffoldPage, ScaffoldTab

pytestmark = pytest.mark.e2e


def test_scaffold_flow_dsl(page: Page, scaffold_page: ScaffoldPage) -> None:
    scaffold_page.goto()
    expect(scaffold_page.heading_locator.first).to_be_visible()
    scaffold_page.generate_from_dsl("A -> B -> C")
    expect(scaffold_page.yaml_output_locator).to_be_visible()
    expect(scaffold_page.yaml_output_locator).to_contain_text("nodes:")
    try:
        parsed_data = yaml.safe_load(scaffold_page.yaml_text())
        assert isinstance(parsed_data, (dict, list))
        nodes = parsed_data.get("nodes", {})
        assert isinstance(nodes, dict)
        for node_name in ["A", "B", "C"]:
            assert node_name in nodes, f"Node '{node_name}' not found in generated YAML"
    except yaml.YAMLError as e:
        pytest.fail(f"Failed to parse YAML: {e}")

def test_scaffold_flow_template(page: Page, scaffold_page: ScaffoldPage) -> None:
    scaffold_page.goto()
    expect(scaffold_page.heading_locator.first).to_be_visible()
    scaffold_page.open_tab(ScaffoldTab.TEMPLATE)
    expect(scaffold_page.pattern_cards_locator).to_have_count(25)

def test_scaffold_flow_blank(page: Page, scaffold_page: ScaffoldPage) -> None:
    scaffold_page.goto()
    expect(scaffold_page.heading_locator.first).to_be_visible()
    scaffold_page.open_tab(ScaffoldTab.BLANK)
    expect(scaffold_page.blank_open_editor_button_locator).to_be_visible()
