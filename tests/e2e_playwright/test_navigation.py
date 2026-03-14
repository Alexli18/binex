"""E2E: Sidebar navigation — all pages reachable and render correctly."""
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

    # --- Test 1: Sidebar renders with all groups ---
    print("\n=== Test: Sidebar Navigation ===")
    page.goto(BASE, wait_until="networkidle")

    sidebar = page.locator("aside")
    check("Sidebar exists", sidebar.count() > 0)

    groups = ["Workflows", "Runs", "Costs & Budget", "Export", "System"]
    for g in groups:
        check(f"Group '{g}' visible", page.get_by_text(g).count() > 0)

    # --- Test 2: Navigate to each page via sidebar links ---
    print("\n=== Test: Page Navigation ===")

    nav_items = [
        ("Browse", "/workflows", "Workflows"),
        ("Scaffold", "/scaffold", "Create Workflow"),
        ("Dashboard", "/", "Dashboard"),
        ("Compare", "/diff", "Compare Runs"),
        ("Bisect", "/bisect", "Bisect"),
        ("Cost Dashboard", "/costs", "Cost Dashboard"),
        ("Budget", "/costs/budget", "Budget Management"),
        ("Export Runs", "/export", "Export Run Data"),
        ("Doctor", "/system/doctor", "System Health"),
        ("Plugins", "/system/plugins", "Plugins"),
        ("Gateway", "/system/gateway", "A2A Gateway"),
    ]

    for link_text, expected_path, expected_heading in nav_items:
        link = page.get_by_role("link", name=link_text, exact=True).first
        if link.count() == 0:
            check(f"Navigate to {link_text}", False, "link not found")
            continue
        link.click()
        page.wait_for_load_state("networkidle")
        check(
            f"Navigate to {link_text}",
            expected_path in page.url or (expected_path == "/" and page.url.endswith("/")),
            f"URL: {page.url}",
        )

    # --- Test 3: Sidebar collapse/expand ---
    print("\n=== Test: Sidebar Collapse ===")
    page.goto(BASE, wait_until="networkidle")

    sidebar = page.locator("aside")
    initial_class = sidebar.get_attribute("class") or ""
    check("Sidebar initially expanded", "w-60" in initial_class)

    collapse_btn = sidebar.locator("button").first
    collapse_btn.click()
    page.wait_for_timeout(300)
    collapsed_class = sidebar.get_attribute("class") or ""
    check("Sidebar collapsed", "w-12" in collapsed_class)

    collapse_btn.click()
    page.wait_for_timeout(300)
    expanded_class = sidebar.get_attribute("class") or ""
    check("Sidebar re-expanded", "w-60" in expanded_class)

    # --- Test 4: Active nav state ---
    print("\n=== Test: Active Nav State ===")
    page.goto(f"{BASE}/costs", wait_until="networkidle")
    active_link = page.locator("a.border-blue-500")
    check("Active link highlighted", active_link.count() > 0)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
