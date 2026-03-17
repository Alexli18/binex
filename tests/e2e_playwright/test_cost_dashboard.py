"""E2E: Cost Dashboard — KPI cards, charts, period selector (standalone page at /costs)."""
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

    # --- Navigate to Cost Dashboard page ---
    print("\n=== Test: Cost Dashboard ===")
    page.goto(f"{BASE}/costs", wait_until="networkidle")
    page.wait_for_timeout(1000)

    # --- Test 1: KPI cards ---
    check("Total Cost card", page.get_by_text("Total Cost").count() > 0)
    check("Avg per Run card", page.get_by_text("Avg per Run").count() > 0)
    check("Total Runs card", page.get_by_text("Total Runs").count() > 0)
    check("Budget Used card", page.get_by_text("Budget Used").count() > 0)

    # --- Test 2: Period selector (shadcn Select, not buttons) ---
    print("\n=== Test: Period Selector ===")
    period_select = page.get_by_label("Select period")
    check("Period selector exists", period_select.count() > 0)

    # Open the select and check options
    if period_select.count() > 0:
        period_select.click()
        page.wait_for_timeout(500)
        for p_text in ["24h", "7d", "30d", "all"]:
            option = page.get_by_role("option", name=p_text, exact=True)
            check(f"Period option '{p_text}' exists", option.count() > 0)
        # Select 30d
        opt_30d = page.get_by_role("option", name="30d", exact=True)
        if opt_30d.count() > 0:
            opt_30d.click()
            page.wait_for_timeout(1000)
            check("30d option selectable", True)

    # --- Test 3: Chart sections exist ---
    print("\n=== Test: Chart Sections ===")
    check("Cost Trend chart", page.get_by_text("Cost Trend").count() > 0)
    check("Cost by Model chart", page.get_by_text("Cost by Model").count() > 0)
    check("Cost by Node chart", page.get_by_text("Cost by Node").count() > 0)

    page.screenshot(path="/tmp/binex_e2e_cost_test.png", full_page=True)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
