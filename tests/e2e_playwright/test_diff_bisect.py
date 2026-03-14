"""E2E: Diff and Bisect pages — UI elements and interaction."""
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

    # --- Test 1: Diff page structure ---
    print("\n=== Test: Diff Page ===")
    page.goto(f"{BASE}/diff", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Diff page loads", page.get_by_text("Compare Runs").count() > 0)

    # Should have two run selectors
    selects = page.locator("select").all()
    check("Two run selectors", len(selects) >= 2, f"found {len(selects)}")

    # Should have Compare button
    compare_btn = page.get_by_role("button", name="Compare").first
    check("Compare button exists", compare_btn.count() > 0)

    # Select same run in both dropdowns and compare
    if len(selects) >= 2:
        options = selects[0].locator("option").all()
        if len(options) > 1:  # first is placeholder
            value = options[1].get_attribute("value") or ""
            if value:
                selects[0].select_option(value)
                selects[1].select_option(value)
                compare_btn.click()
                page.wait_for_timeout(2000)
                # Should show results or error
                has_result = page.locator("table").count() > 0 or page.get_by_text("node_diffs").count() > 0 or page.get_by_text("Status").count() > 1
                check("Diff result rendered", has_result)

    page.screenshot(path="/tmp/binex_e2e_diff.png", full_page=True)

    # --- Test 2: Bisect page structure ---
    print("\n=== Test: Bisect Page ===")
    page.goto(f"{BASE}/bisect", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Bisect page loads", page.get_by_text("Bisect").count() > 0)

    # Threshold slider
    slider = page.locator("input[type='range']").first
    check("Threshold slider exists", slider.count() > 0)

    if slider.count() > 0:
        value = slider.get_attribute("value")
        check("Threshold default 0.9", value == "0.9", f"value={value}")

    # Find Divergence button
    find_btn = page.get_by_role("button", name="Find Divergence").first
    check("Find Divergence button", find_btn.count() > 0)

    page.screenshot(path="/tmp/binex_e2e_bisect.png", full_page=True)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
