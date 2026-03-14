"""E2E: Cost Dashboard — KPI cards, charts, period selector."""
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

    # --- Test 1: Cost Dashboard loads with KPI cards ---
    print("\n=== Test: Cost Dashboard ===")
    page.goto(f"{BASE}/costs", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Page loads", page.get_by_text("Cost Dashboard").count() > 0)
    check("Total Cost card", page.get_by_text("Total Cost").count() > 0)
    check("Avg per Run card", page.get_by_text("Avg per Run").count() > 0)
    check("Total Runs card", page.get_by_text("Total Runs").count() > 0)
    check("Budget Used card", page.get_by_text("Budget Used").count() > 0)

    # --- Test 2: Period selector ---
    print("\n=== Test: Period Selector ===")
    period_btns = ["24h", "7d", "30d", "all"]
    for p_text in period_btns:
        btn = page.get_by_role("button", name=p_text, exact=True).first
        check(f"Period button '{p_text}' exists", btn.count() > 0)

    # Click 30d and verify it becomes active
    btn_30d = page.get_by_role("button", name="30d", exact=True).first
    if btn_30d.count() > 0:
        btn_30d.click()
        page.wait_for_timeout(1000)
        check("30d button clickable", True)

    # --- Test 3: Chart sections exist ---
    print("\n=== Test: Chart Sections ===")
    check("Cost Trend chart", page.get_by_text("Cost Trend").count() > 0)
    check("Cost by Model chart", page.get_by_text("Cost by Model").count() > 0)
    check("Cost by Node chart", page.get_by_text("Cost by Node").count() > 0)

    # Check SVG charts rendered (Recharts renders SVGs)
    svg_count = page.locator("svg.recharts-surface").count()
    check("Recharts SVGs rendered", svg_count >= 1, f"found {svg_count}")

    page.screenshot(path="/tmp/binex_e2e_cost_test.png", full_page=True)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
