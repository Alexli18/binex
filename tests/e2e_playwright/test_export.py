"""E2E: Export page — format toggle, run selection."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8420"
PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {name}")
    else:
        FAILED += 1
        print(f"  FAIL  {name} — {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    print("\n=== Test: Export Page ===")
    page.goto(f"{BASE}/export", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Export page loads", page.get_by_text("Export").count() > 0)

    # Format buttons
    csv_btn = page.get_by_role("button", name="CSV").first
    json_btn = page.get_by_role("button", name="JSON").first
    check("CSV button exists", csv_btn.count() > 0)
    check("JSON button exists", json_btn.count() > 0)

    # Include artifacts checkbox
    checkbox = page.locator("input[type='checkbox']").first
    check("Include artifacts checkbox", checkbox.count() > 0)

    # Download button
    download_btn = page.get_by_role("button", name="Download").first
    check("Download button exists", download_btn.count() > 0)

    page.screenshot(path="/tmp/binex_e2e_export.png", full_page=True)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
