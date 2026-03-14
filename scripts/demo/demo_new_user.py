"""Demo: New user experience — create workflow from scratch in Visual Editor.

Run with server started from a CLEAN directory:
  mkdir /tmp/binex_fresh && cd /tmp/binex_fresh && binex ui --no-browser
Then: python scripts/demo/demo_new_user.py
"""
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8420"
VIDEO_DIR = "/tmp/binex_demo_fresh"
USER_INPUT = "Дай совет, как красиво одеваться."


def slow(ms=1200):
    time.sleep(ms / 1000)


def drag_from_palette(page, label: str, target_x: int, target_y: int):
    """Drag a node type from palette to canvas."""
    item = page.get_by_text(label, exact=True).first
    if item.count() > 0:
        box = item.bounding_box()
        if box:
            sx = box["x"] + box["width"] / 2
            sy = box["y"] + box["height"] / 2
            page.mouse.move(sx, sy)
            slow(300)
            page.mouse.down()
            page.mouse.move(target_x, target_y, steps=25)
            slow(200)
            page.mouse.up()
            slow(600)
            return True
    return False


def close_expanded_node(page):
    """Close expanded node by clicking the X button."""
    # The X button is inside the node header, it's a button with X svg
    x_btn = page.locator(".react-flow__node.selected button:has-text('×')").first
    if x_btn.count() > 0:
        x_btn.click(force=True)
        slow(400)
        return
    # Fallback: press Escape
    page.keyboard.press("Escape")
    slow(400)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=150)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()

    # === 1. Dashboard — fresh install ===
    print("1. Dashboard (fresh)")
    page.goto(BASE, wait_until="networkidle")
    slow(2500)

    # === 2. Go to Editor ===
    print("2. Open Editor")
    page.get_by_role("link", name="Editor", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1500)

    # === 3. Click "+ New" ===
    print("3. Click + New")
    new_btn = page.get_by_role("button", name="+ New").first
    if new_btn.count() > 0:
        new_btn.click()
        slow(1500)

    # === 4. Drag nodes — top to bottom pipeline ===
    print("4. Drag & drop nodes")
    # Canvas starts ~450px from left. Place nodes vertically, spaced 100px apart
    cx = 750  # center of canvas
    drag_from_palette(page, "Human Input", cx, 100)
    slow(300)
    drag_from_palette(page, "LLM Agent", cx, 220)
    slow(300)
    drag_from_palette(page, "LLM Agent", cx, 340)
    slow(300)
    drag_from_palette(page, "LLM Agent", cx, 460)
    slow(300)
    drag_from_palette(page, "Human Output", cx, 580)
    slow(1000)

    # === 5. Zoom out to see all nodes ===
    print("5. Zoom out")
    zoom_out = page.locator("button.react-flow__controls-zoomout").first
    if zoom_out.count() > 0:
        zoom_out.click()
        slow(300)
        zoom_out.click()
        slow(300)
        zoom_out.click()
        slow(500)
    slow(1000)

    # === 6. Connect nodes ===
    print("6. Connect nodes")
    nodes = page.locator(".react-flow__node").all()
    for i in range(len(nodes) - 1):
        src = nodes[i]
        tgt = nodes[i + 1]
        src_box = src.bounding_box()
        tgt_box = tgt.bounding_box()
        if src_box and tgt_box:
            sx = src_box["x"] + src_box["width"] / 2
            sy = src_box["y"] + src_box["height"] - 2
            tx = tgt_box["x"] + tgt_box["width"] / 2
            ty = tgt_box["y"] + 2
            page.mouse.move(sx, sy)
            slow(200)
            page.mouse.down()
            page.mouse.move(tx, ty, steps=15)
            page.mouse.up()
            slow(400)
    slow(1500)

    # === 7. Configure LLM nodes ===
    print("7. Configure nodes")
    nodes = page.locator(".react-flow__node").all()

    # Planner (index 1 — second node)
    if len(nodes) > 1:
        print("   Configuring planner...")
        nodes[1].click()
        slow(1000)

        # Rename
        name_input = page.locator(".react-flow__node.selected input[type='text']").first
        if name_input.count() > 0:
            name_input.triple_click()
            name_input.type("planner", delay=60)
            slow(300)

        # Model
        model_dropdown = page.locator(".react-flow__node.selected select").first
        if model_dropdown.count() > 0:
            model_dropdown.select_option("gemini-2.5-flash")
            slow(500)

        # Prompt
        prompt_select = page.locator(".react-flow__node.selected select").nth(1)
        if prompt_select.count() > 0:
            prompt_select.select_option("wf-planner")
            slow(1000)

        close_expanded_node(page)

    # Researcher (index 2)
    if len(nodes) > 2:
        print("   Configuring researcher...")
        nodes[2].click()
        slow(1000)

        name_input = page.locator(".react-flow__node.selected input[type='text']").first
        if name_input.count() > 0:
            name_input.triple_click()
            name_input.type("researcher", delay=60)
            slow(300)

        model_dropdown = page.locator(".react-flow__node.selected select").first
        if model_dropdown.count() > 0:
            model_dropdown.select_option("gemini-2.5-flash")
            slow(500)

        prompt_select = page.locator(".react-flow__node.selected select").nth(1)
        if prompt_select.count() > 0:
            prompt_select.select_option("gen-researcher")
            slow(1000)

        close_expanded_node(page)

    # Summarizer (index 3)
    if len(nodes) > 3:
        print("   Configuring summarizer...")
        nodes[3].click()
        slow(1000)

        name_input = page.locator(".react-flow__node.selected input[type='text']").first
        if name_input.count() > 0:
            name_input.triple_click()
            name_input.type("summarizer", delay=60)
            slow(300)

        model_dropdown = page.locator(".react-flow__node.selected select").first
        if model_dropdown.count() > 0:
            model_dropdown.select_option("gemini-2.5-flash")
            slow(500)

        prompt_select = page.locator(".react-flow__node.selected select").nth(1)
        if prompt_select.count() > 0:
            prompt_select.select_option("sup-summarizer-brief")
            slow(1000)

        close_expanded_node(page)

    slow(1500)

    # === 8. Zoom to fit ===
    print("8. Fit view")
    fit_btn = page.locator("button.react-flow__controls-fitview").first
    if fit_btn.count() > 0:
        fit_btn.click()
        slow(1500)

    # === 9. Show YAML ===
    print("9. YAML preview")
    yaml_btn = page.get_by_role("button", name="YAML").first
    if yaml_btn.count() > 0:
        yaml_btn.click()
        slow(2500)

    # === 10. Back to Visual + Run ===
    print("10. Visual + Run")
    visual_btn = page.get_by_role("button", name="Visual").first
    if visual_btn.count() > 0:
        visual_btn.click()
        try:
            page.wait_for_selector(".react-flow__node", timeout=5000)
        except Exception:
            pass
        slow(2000)

    print("11. Click Run")
    slow(1000)
    run_btn = page.locator("button.bg-blue-600:has-text('Run')").first
    if run_btn.count() > 0:
        run_btn.click()
        print("    Run clicked!")
        slow(3000)

    # === 11. Human Input modal ===
    print("12. Human Input...")
    try:
        page.wait_for_selector("textarea", timeout=30000)
        slow(1000)
        textarea = page.locator("textarea").first
        if textarea.count() > 0:
            textarea.click()
            textarea.type(USER_INPUT, delay=50)
            slow(1000)
        submit_btn = page.get_by_role("button", name="Submit").first
        if submit_btn.count() > 0:
            submit_btn.click()
            print("    Submitted!")
            slow(1000)
    except Exception as e:
        print(f"    Input issue: {e}")

    # === 12. Wait for Human Output ===
    print("13. Watching execution...")
    try:
        page.wait_for_selector("text=Workflow Output", timeout=300000)
        print("14. Human Output!")
        slow(8000)
        close_btn = page.get_by_role("button", name="Close").first
        if close_btn.count() > 0:
            close_btn.click()
            slow(2000)
    except Exception:
        slow(10000)

    # === 13. Debug/Trace/Lineage ===
    run_id = None
    if "/runs/" in page.url:
        run_id = page.url.split("/runs/")[-1].split("/")[0].split("?")[0]

    if run_id:
        print("15. Debug")
        page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
        slow(1500)
        node_btns = page.locator("button[class*='text-left']").all()
        for btn in node_btns[:4]:
            btn.click()
            slow(1200)

        print("16. Trace")
        page.goto(f"{BASE}/runs/{run_id}/trace", wait_until="networkidle")
        slow(2500)

        print("17. Lineage")
        page.goto(f"{BASE}/runs/{run_id}/lineage", wait_until="networkidle")
        slow(2500)

    # === End ===
    print("18. Dashboard")
    page.goto(BASE, wait_until="networkidle")
    slow(2000)

    video_path = page.video.path()
    context.close()
    browser.close()

    print(f"\n✅ Demo recorded: {video_path}")
    print(f"Convert: ffmpeg -i '{video_path}' -c:v libx264 -preset fast -crf 22 /tmp/binex_demo_fresh/new_user_demo.mp4")
