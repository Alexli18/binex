"""Demo: Build workflow in Visual Editor → Run → Debug → Replay (1-2 min).

Run with server already started: python scripts/demo/demo_build_debug.py
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

    # === 1. Open Editor in Visual mode ===
    print("1/8 Open Editor")
    page.goto(f"{BASE}/editor", wait_until="networkidle")
    slow(1000)

    visual_btn = page.get_by_role("button", name="Visual").first
    if visual_btn.count() > 0:
        visual_btn.click()
        slow(1500)

    # === 2. Drag & drop nodes from palette ===
    print("2/8 Drag nodes")

    # Get palette items and canvas
    palette_items = {
        "LLM Agent": (700, 200),
        "Human Input": (700, 100),
    }

    for label, (x, y) in palette_items.items():
        item = page.get_by_text(label, exact=True).first
        if item.count() > 0:
            box = item.bounding_box()
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                slow(300)
                page.mouse.down()
                page.mouse.move(x, y, steps=20)
                page.mouse.up()
                slow(500)

    slow(1500)

    # === 3. Click on a node to edit ===
    print("3/8 Edit node")
    # Click on a node in canvas
    page.mouse.click(700, 200)
    slow(2000)

    # === 4. Switch to YAML to see generated code ===
    print("4/8 YAML view")
    yaml_btn = page.get_by_role("button", name="YAML").first
    if yaml_btn.count() > 0:
        yaml_btn.click()
        slow(2000)

    # === 5. Go to a completed run's Debug page ===
    print("5/8 Debug page")
    page.goto(BASE, wait_until="networkidle")
    slow(500)

    run_link = page.locator("a[href*='/runs/']").first
    run_id = None
    if run_link.count() > 0:
        href = run_link.get_attribute("href") or ""
        run_id = href.split("/runs/")[-1].split("/")[0] if "/runs/" in href else None
        run_link.click()
        page.wait_for_load_state("networkidle")
        slow(1000)

    if run_id:
        page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
        slow(1500)

        # Click on nodes to show details
        node_btns = page.locator("button[class*='text-left']").all()
        for i, btn in enumerate(node_btns[:3]):
            btn.click()
            slow(1500)

        # === 6. Trace timeline ===
        print("6/8 Trace")
        page.goto(f"{BASE}/runs/{run_id}/trace", wait_until="networkidle")
        slow(2000)

        # === 7. Lineage ===
        print("7/8 Lineage")
        page.goto(f"{BASE}/runs/{run_id}/lineage", wait_until="networkidle")
        slow(2000)

        # === 8. Replay ===
        print("8/8 Replay modal")
        page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
        slow(1000)

        # Click first node
        node_btns = page.locator("button[class*='text-left']").all()
        if len(node_btns) > 1:
            node_btns[1].click()
            slow(1000)

        # Click Replay button
        replay_btn = page.get_by_role("button", name="Replay").first
        if replay_btn.count() > 0:
            replay_btn.click()
            slow(2000)

            # Close modal
            cancel_btn = page.get_by_role("button", name="Cancel").first
            if cancel_btn.count() > 0:
                cancel_btn.click()
                slow(500)

    slow(1500)

    video_path = page.video.path()
    context.close()
    browser.close()

    print(f"\n✅ Demo recorded: {video_path}")
    print(f"Convert: ffmpeg -i '{video_path}' -c:v libx264 -preset fast -crf 22 /tmp/binex_demo/build_debug.mp4")
