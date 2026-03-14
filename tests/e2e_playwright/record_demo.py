"""Record a demo video of Binex Web UI — full walkthrough."""
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8420"
VIDEO_DIR = "/tmp/binex_demo"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()

    def slow(ms=800):
        time.sleep(ms / 1000)

    # === 1. Dashboard ===
    print("1. Dashboard...")
    page.goto(BASE, wait_until="networkidle")
    slow(2000)

    # === 2. Navigate to Editor ===
    print("2. Editor...")
    page.get_by_role("link", name="Editor", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1500)

    # === 3. Switch to Visual mode ===
    print("3. Visual mode...")
    visual_btn = page.get_by_role("button", name="Visual").first
    if visual_btn.count() > 0:
        visual_btn.click()
        slow(1500)

    # === 4. Show node palette ===
    print("4. Node palette visible...")
    slow(1000)

    # === 5. Switch to YAML mode ===
    print("5. YAML mode...")
    yaml_btn = page.get_by_role("button", name="YAML").first
    if yaml_btn.count() > 0:
        yaml_btn.click()
        slow(1500)

    # === 6. Navigate to Scaffold ===
    print("6. Scaffold...")
    page.get_by_role("link", name="Scaffold", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1000)

    # Type DSL
    dsl_input = page.locator("input[placeholder*='A -> B']").first
    if dsl_input.count() > 0:
        dsl_input.fill("planner -> researcher -> summarizer")
        slow(500)
        page.get_by_role("button", name="Generate").first.click()
        slow(2000)

    # === 7. Template tab ===
    print("7. Templates...")
    template_tab = page.get_by_text("Template", exact=True).first
    if template_tab.count() > 0:
        template_tab.click()
        slow(1500)

    # === 8. Cost Dashboard ===
    print("8. Cost Dashboard...")
    page.get_by_role("link", name="Cost Dashboard").first.click()
    page.wait_for_load_state("networkidle")
    slow(2000)

    # Switch period
    btn_30d = page.get_by_role("button", name="30d", exact=True).first
    if btn_30d.count() > 0:
        btn_30d.click()
        slow(1000)

    # === 9. Dashboard — click a run ===
    print("9. Run detail...")
    page.get_by_role("link", name="Dashboard", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1000)

    # Click first run link
    run_link = page.locator("a[href*='/runs/']").first
    if run_link.count() > 0:
        run_link.click()
        page.wait_for_load_state("networkidle")
        slow(2000)

        # Get run ID from URL
        run_id = page.url.split("/runs/")[-1].split("/")[0] if "/runs/" in page.url else None

        if run_id:
            # === 10. Debug ===
            print("10. Debug...")
            page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
            slow(1500)

            # Click first node
            nodes = page.locator("[class*='cursor-pointer']").all()
            if len(nodes) > 1:
                nodes[1].click()
                slow(1500)

            # === 11. Trace ===
            print("11. Trace...")
            page.goto(f"{BASE}/runs/{run_id}/trace", wait_until="networkidle")
            slow(2000)

            # === 12. Diagnose ===
            print("12. Diagnose...")
            page.goto(f"{BASE}/runs/{run_id}/diagnose", wait_until="networkidle")
            slow(1500)

            # === 13. Lineage ===
            print("13. Lineage...")
            page.goto(f"{BASE}/runs/{run_id}/lineage", wait_until="networkidle")
            slow(2000)

    # === 14. System pages ===
    print("14. Doctor...")
    page.goto(f"{BASE}/system/doctor", wait_until="networkidle")
    slow(1500)

    print("15. Plugins...")
    page.goto(f"{BASE}/system/plugins", wait_until="networkidle")
    slow(1500)

    print("16. Gateway...")
    page.goto(f"{BASE}/system/gateway", wait_until="networkidle")
    slow(1500)

    # === End ===
    print("17. Back to Dashboard...")
    page.goto(BASE, wait_until="networkidle")
    slow(1500)

    # Close context to finalize video
    context.close()
    browser.close()

    print(f"\n✅ Demo video saved to {VIDEO_DIR}/")
    print("Look for the .webm file in that directory")
