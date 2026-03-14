"""E2E: System pages — Doctor, Plugins, Gateway."""
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

    # --- Test 1: Doctor page ---
    print("\n=== Test: Doctor Page ===")
    page.goto(f"{BASE}/system/doctor", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Doctor page loads", page.get_by_text("System Health").count() > 0)

    # Should have health check cards
    # Look for status indicators (ok or error)
    cards = page.locator("[class*='rounded']").all()
    check("Health check cards rendered", len(cards) > 2, f"found {len(cards)} elements")

    page.screenshot(path="/tmp/binex_e2e_doctor.png", full_page=True)

    # --- Test 2: Plugins page ---
    print("\n=== Test: Plugins Page ===")
    page.goto(f"{BASE}/system/plugins", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Plugins page loads", page.get_by_text("Plugins").count() > 0)

    # Should list built-in adapters
    has_local = page.get_by_text("local").count() > 0
    has_llm = page.get_by_text("llm").count() > 0
    check("Local adapter listed", has_local)
    check("LLM adapter listed", has_llm)

    # Built-in badge
    builtin_badges = page.get_by_text("Built-in").count()
    check("Built-in badges shown", builtin_badges >= 1, f"found {builtin_badges}")

    page.screenshot(path="/tmp/binex_e2e_plugins.png", full_page=True)

    # --- Test 3: Gateway page ---
    print("\n=== Test: Gateway Page ===")
    page.goto(f"{BASE}/system/gateway", wait_until="networkidle")
    page.wait_for_timeout(1000)

    check("Gateway page loads", page.get_by_text("A2A Gateway").count() > 0)

    # Gateway should be offline (we didn't start it)
    has_offline = page.get_by_text("offline", exact=False).count() > 0 or page.get_by_text("Offline").count() > 0
    check("Gateway shows offline status", has_offline)

    page.screenshot(path="/tmp/binex_e2e_gateway.png", full_page=True)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
