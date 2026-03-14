"""Reconnaissance: screenshot all pages to verify they load."""
from playwright.sync_api import sync_playwright

PAGES = [
    ("/", "dashboard"),
    ("/workflows", "workflow_browse"),
    ("/editor", "editor"),
    ("/scaffold", "scaffold"),
    ("/diff", "diff"),
    ("/bisect", "bisect"),
    ("/costs", "cost_dashboard"),
    ("/costs/budget", "budget"),
    ("/export", "export"),
    ("/system/doctor", "doctor"),
    ("/system/plugins", "plugins"),
    ("/system/gateway", "gateway"),
]

BASE = "http://localhost:8420"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})

    results = []
    for path, name in PAGES:
        url = f"{BASE}{path}"
        try:
            page.goto(url, wait_until="networkidle", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.screenshot(path=f"/tmp/binex_e2e_{name}.png", full_page=True)
            # Check page has content (not blank)
            title = page.locator("h1, h2").first.text_content() if page.locator("h1, h2").count() > 0 else "(no heading)"
            results.append(f"OK  {path:25s} → {title}")
        except Exception as e:
            results.append(f"ERR {path:25s} → {str(e)[:80]}")

    browser.close()

    print("\n=== Page Load Results ===")
    for r in results:
        print(r)
    print(f"\nTotal: {len(results)} pages checked")
    ok_count = sum(1 for r in results if r.startswith("OK"))
    print(f"Passed: {ok_count}/{len(results)}")
