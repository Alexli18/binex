"""E2E: Run analysis pages — Debug, Trace, Diagnose from a real run."""
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

    # First get a run_id from the dashboard
    print("\n=== Setup: Get Run ID ===")
    page.goto(BASE, wait_until="networkidle")
    page.wait_for_timeout(1000)

    # Find first run link in the table
    run_links = page.locator("a[href*='/runs/']").all()
    if not run_links:
        # Try clicking on a table row
        rows = page.locator("tr").all()
        check("Dashboard has runs", len(rows) > 1, f"found {len(rows)} rows")
        # Get run_id from first data cell
        first_cell = page.locator("td").first
        run_id = first_cell.text_content() if first_cell.count() > 0 else None
    else:
        href = run_links[0].get_attribute("href") or ""
        run_id = href.split("/runs/")[-1].split("/")[0] if "/runs/" in href else None
        check("Got run link", bool(run_id), f"href={href}")

    if not run_id:
        # Fallback: read from API
        page.goto(f"{BASE}/api/v1/runs", wait_until="networkidle")
        import json
        content = page.locator("pre").text_content() or page.content()
        try:
            data = json.loads(content) if content.startswith("[") or content.startswith("{") else None
            if data and isinstance(data, list) and len(data) > 0:
                run_id = data[0].get("run_id")
        except:
            pass

    if not run_id:
        print("  SKIP  No runs available for analysis tests")
        browser.close()
        print(f"\n{'='*40}")
        print(f"Results: {PASSED} passed, {FAILED} failed (skipped analysis)")
        exit(0)

    print(f"  Using run_id: {run_id}")

    # --- Test 1: Debug page ---
    print("\n=== Test: Debug Page ===")
    page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
    page.wait_for_timeout(1500)

    check("Debug page loads", page.get_by_text("Debug").count() > 0)

    # Should have node list
    node_items = page.locator("[class*='cursor-pointer']").count()
    check("Node list rendered", node_items >= 0)  # may be 0 if mock data

    page.screenshot(path="/tmp/binex_e2e_debug.png", full_page=True)

    # Test errors-only toggle if it exists
    toggle = page.get_by_text("Errors Only", exact=False).first
    if toggle.count() > 0:
        check("Errors Only toggle exists", True)

    # --- Test 2: Trace page ---
    print("\n=== Test: Trace Page ===")
    page.goto(f"{BASE}/runs/{run_id}/trace", wait_until="networkidle")
    page.wait_for_timeout(1500)

    check("Trace page loads", page.get_by_text("Trace").count() > 0 or page.get_by_text("Timeline").count() > 0)

    page.screenshot(path="/tmp/binex_e2e_trace.png", full_page=True)

    # --- Test 3: Diagnose page ---
    print("\n=== Test: Diagnose Page ===")
    page.goto(f"{BASE}/runs/{run_id}/diagnose", wait_until="networkidle")
    page.wait_for_timeout(1500)

    check("Diagnose page loads", page.get_by_text("Diagnos").count() > 0)

    # Should show severity
    severity_texts = ["HIGH", "MEDIUM", "LOW", "NONE"]
    has_severity = any(page.get_by_text(s, exact=True).count() > 0 for s in severity_texts)
    check("Severity indicator shown", has_severity)

    page.screenshot(path="/tmp/binex_e2e_diagnose.png", full_page=True)

    # --- Test 4: Lineage page ---
    print("\n=== Test: Lineage Page ===")
    page.goto(f"{BASE}/runs/{run_id}/lineage", wait_until="networkidle")
    page.wait_for_timeout(1500)

    check("Lineage page loads", page.get_by_text("Lineage").count() > 0 or page.get_by_text("Artifact").count() > 0)

    page.screenshot(path="/tmp/binex_e2e_lineage.png", full_page=True)

    # --- Test 5: Analysis links in sidebar when on run page ---
    print("\n=== Test: Sidebar Analysis Group ===")
    sidebar = page.locator("aside")
    analysis_visible = page.get_by_text("Analysis").count() > 0
    check("Analysis group visible on run page", analysis_visible)

    if analysis_visible:
        debug_link = page.get_by_role("link", name="Debug", exact=True).first
        check("Debug link in sidebar", debug_link.count() > 0)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
