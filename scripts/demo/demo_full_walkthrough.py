"""Demo: Full walkthrough of Binex Web UI (2-3 min).

Run with server already started: python scripts/demo/demo_full_walkthrough.py
Records WebM video to /tmp/binex_demo/
"""
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8420"
VIDEO_DIR = "/tmp/binex_demo"


def slow(ms=1200):
    time.sleep(ms / 1000)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()

    # === 1. Dashboard ===
    print("1/12 Dashboard")
    page.goto(BASE, wait_until="networkidle")
    slow(2000)

    # Scroll down to show runs
    page.mouse.wheel(0, 300)
    slow(1000)
    page.mouse.wheel(0, -300)
    slow(500)

    # === 2. Workflow Browse ===
    print("2/12 Browse")
    page.get_by_role("link", name="Browse", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1500)

    # === 3. Editor — YAML mode ===
    print("3/12 Editor (YAML)")
    page.get_by_role("link", name="Editor", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(2000)

    # === 4. Editor — Visual mode ===
    print("4/12 Editor (Visual)")
    visual_btn = page.get_by_role("button", name="Visual").first
    if visual_btn.count() > 0:
        visual_btn.click()
        slow(2000)

    # Hover over palette items
    for label in ["LLM Agent", "Local Script", "Human Approve", "Human Input", "Human Output", "A2A Agent"]:
        item = page.get_by_text(label, exact=True).first
        if item.count() > 0:
            item.hover()
            slow(400)

    slow(1000)

    # Back to YAML
    yaml_btn = page.get_by_role("button", name="YAML").first
    if yaml_btn.count() > 0:
        yaml_btn.click()
        slow(1500)

    # === 5. Scaffold — DSL ===
    print("5/12 Scaffold (DSL)")
    page.get_by_role("link", name="Scaffold", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1000)

    dsl_input = page.locator("input[placeholder*='A -> B']").first
    if dsl_input.count() > 0:
        dsl_input.click()
        dsl_input.type("A -> B, C -> D", delay=80)
        slow(500)
        page.get_by_role("button", name="Generate").first.click()
        slow(2000)

    # === 6. Scaffold — Templates ===
    print("6/12 Scaffold (Templates)")
    template_tab = page.get_by_text("Template", exact=True).first
    if template_tab.count() > 0:
        template_tab.click()
        slow(2000)

    # === 7. Cost Dashboard ===
    print("7/12 Cost Dashboard")
    page.get_by_role("link", name="Cost Dashboard").first.click()
    page.wait_for_load_state("networkidle")
    slow(2000)

    # Switch periods
    for period in ["24h", "30d", "7d"]:
        btn = page.get_by_role("button", name=period, exact=True).first
        if btn.count() > 0:
            btn.click()
            slow(800)

    # === 8. Run Detail (click first run) ===
    print("8/12 Run Detail")
    page.get_by_role("link", name="Dashboard", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1000)

    run_link = page.locator("a[href*='/runs/']").first
    run_id = None
    if run_link.count() > 0:
        href = run_link.get_attribute("href") or ""
        run_id = href.split("/runs/")[-1].split("/")[0] if "/runs/" in href else None
        run_link.click()
        page.wait_for_load_state("networkidle")
        slow(2000)

    if run_id:
        # === 9. Debug ===
        print("9/12 Debug")
        page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
        slow(1500)

        # Click on a node
        node_btns = page.locator("button[class*='text-left']").all()
        if len(node_btns) > 1:
            node_btns[1].click()
            slow(2000)

        # === 10. Trace ===
        print("10/12 Trace")
        page.goto(f"{BASE}/runs/{run_id}/trace", wait_until="networkidle")
        slow(2000)

        # === 11. Diagnose ===
        print("11/12 Diagnose")
        page.goto(f"{BASE}/runs/{run_id}/diagnose", wait_until="networkidle")
        slow(1500)

        # === 12. Lineage ===
        print("12/12 Lineage")
        page.goto(f"{BASE}/runs/{run_id}/lineage", wait_until="networkidle")
        slow(2000)

    # === System pages ===
    print("    Doctor")
    page.goto(f"{BASE}/system/doctor", wait_until="networkidle")
    slow(1500)

    print("    Plugins")
    page.goto(f"{BASE}/system/plugins", wait_until="networkidle")
    slow(1500)

    # === End — back to Dashboard ===
    print("    Back to Dashboard")
    page.goto(BASE, wait_until="networkidle")
    slow(2000)

    # Finalize video
    video_path = page.video.path()
    context.close()
    browser.close()

    print(f"\n✅ Demo recorded: {video_path}")
    print(f"Convert to MP4: ffmpeg -i '{video_path}' -c:v libx264 -preset fast -crf 22 /tmp/binex_demo/full_walkthrough.mp4")
