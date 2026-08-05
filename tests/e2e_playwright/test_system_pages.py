"""E2E: System pages — Doctor, Plugins, Gateway."""

from playwright.sync_api import Page, expect


def test_system_page_doctor(page: Page) -> None:
    page.goto("/system/doctor")
    expect(page.get_by_role("heading", name="System Health").first).to_be_visible()
    cards = page.locator("[data-testid^='doctor-check-']")
    expect(cards).to_have_count(4)

def test_system_page_plugins(page: Page) -> None:
    page.goto("/system/plugins")
    expect(page.get_by_role("heading", name="Plugins & Adapters").first).to_be_visible()
    adapters = page.locator("[data-testid^='plugins-adapter-']")
    expect(adapters).to_have_count(8)

def test_system_page_gateway(page: Page) -> None:
    page.goto("/system/gateway")
    expect(page.get_by_role("heading", name="A2A Gateway").first).to_be_visible()
    has_offline = page.get_by_test_id("gateway-status-offline")
    expect(has_offline).to_be_visible()
    expect(has_offline).to_contain_text("Offline")
