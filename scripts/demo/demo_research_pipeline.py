"""Demo: Research pipeline flow — create, run, see results (1 min).

Run with server already started: python scripts/demo/demo_research_pipeline.py
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

    # === 1. Scaffold — create research workflow ===
    print("1/6 Scaffold")
    page.goto(f"{BASE}/scaffold", wait_until="networkidle")
    slow(1500)

    dsl_input = page.locator("input[placeholder*='A -> B']").first
    if dsl_input.count() > 0:
        dsl_input.click()
        dsl_input.type("input -> planner -> researcher -> summarizer -> output", delay=60)
        slow(500)
        page.get_by_role("button", name="Generate").first.click()
        slow(2500)

    # === 2. Open in Editor ===
    print("2/6 Open in Editor")
    open_btn = page.get_by_role("button", name="Open in Editor").first
    if open_btn.count() > 0:
        open_btn.click()
        page.wait_for_load_state("networkidle")
        slow(2000)

    # === 3. Switch to Visual mode to see the graph ===
    print("3/6 Visual mode")
    visual_btn = page.get_by_role("button", name="Visual").first
    if visual_btn.count() > 0:
        visual_btn.click()
        slow(2000)

    # === 4. Show Cost estimate ===
    print("4/6 Cost estimate")
    cost_btn = page.locator("button:has-text('Cost')").first
    if cost_btn.count() > 0:
        cost_btn.click()
        slow(1500)

    # === 5. Go to a completed run to show results ===
    print("5/6 Show completed run")
    page.goto(BASE, wait_until="networkidle")
    slow(1000)

    # Find a completed run
    run_links = page.locator("a[href*='/runs/']").all()
    run_id = None
    for link in run_links[:5]:
        href = link.get_attribute("href") or ""
        if "/runs/" in href:
            rid = href.split("/runs/")[-1].split("/")[0]
            link.click()
            page.wait_for_load_state("networkidle")
            slow(1000)
            # Check if completed
            if page.get_by_text("completed").count() > 0:
                run_id = rid
                break
            page.goto(BASE, wait_until="networkidle")
            slow(500)

    if run_id:
        slow(2000)

        # === 6. Debug — show what each node got ===
        print("6/6 Debug details")
        page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
        slow(1500)

        # Click through nodes
        node_btns = page.locator("button[class*='text-left']").all()
        for btn in node_btns[:4]:
            btn.click()
            slow(1500)
            # Scroll down to see artifacts
            page.mouse.wheel(0, 200)
            slow(500)
            page.mouse.wheel(0, -200)
            slow(300)

    slow(2000)

    video_path = page.video.path()
    context.close()
    browser.close()

    print(f"\n✅ Demo recorded: {video_path}")
    print(f"Convert: ffmpeg -i '{video_path}' -c:v libx264 -preset fast -crf 22 /tmp/binex_demo/research_pipeline.mp4")
