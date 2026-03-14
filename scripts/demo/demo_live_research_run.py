"""Demo: Full live research workflow — everything through UI, no API cheats.

Run with server already started: python scripts/demo/demo_live_research_run.py
"""
import time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8420"
VIDEO_DIR = "/tmp/binex_demo"
USER_INPUT = "Дай совет, как красиво одеваться."


def slow(ms=1200):
    time.sleep(ms / 1000)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=200)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()

    # === 1. Dashboard ===
    print("1. Dashboard")
    page.goto(BASE, wait_until="networkidle")
    slow(2000)

    # === 2. Go to Editor ===
    print("2. Editor")
    page.get_by_role("link", name="Editor", exact=True).first.click()
    page.wait_for_load_state("networkidle")
    slow(1500)

    # === 3. Click on ollama-research.yaml in file sidebar ===
    print("3. Select workflow file")
    file_btn = page.get_by_text("ollama-research", exact=False).first
    if file_btn.count() > 0:
        file_btn.click()
        slow(2000)
    else:
        print("   File not found in sidebar, trying other files...")
        # Try any available file
        file_btns = page.locator("button[class*='text-left'][class*='truncate']").all()
        if file_btns:
            file_btns[0].click()
            slow(2000)

    # === 4. Show YAML ===
    print("4. YAML view")
    slow(1500)

    # === 5. Switch to Visual mode ===
    print("5. Visual mode")
    visual_btn = page.get_by_role("button", name="Visual").first
    if visual_btn.count() > 0:
        visual_btn.click()
        # Wait for ReactFlow to render the graph
        try:
            page.wait_for_selector(".react-flow__node", timeout=10000)
        except Exception:
            pass
        slow(3000)

    # === 6. Click Run ===
    print("6. Click Run")
    slow(2000)
    # Use exact CSS class to find the Run button
    run_btn = page.locator("button.bg-blue-600:has-text('Run')").first
    if run_btn.count() > 0:
        try:
            run_btn.wait_for(state="visible", timeout=5000)
            run_btn.click()
            print("   Run clicked!")
        except Exception as e:
            print(f"   Run button issue: {e}")
        slow(3000)
    else:
        print("   Run button disabled, trying to save first...")
        save_btn = page.get_by_role("button", name="Save").first
        if save_btn.count() > 0:
            save_btn.click()
            slow(1000)
        run_btn = page.get_by_role("button", name="Run").first
        if run_btn.count() > 0:
            run_btn.click()
            slow(3000)

    # === 7. Wait for Human Input modal ===
    print("7. Waiting for Human Input modal...")
    try:
        # Wait for modal — could be "Input Required" or textarea
        page.wait_for_selector("textarea", timeout=30000)
        slow(1000)

        # Type the input
        print("8. Typing input...")
        textarea = page.locator("textarea").first
        if textarea.count() > 0:
            textarea.click()
            textarea.type(USER_INPUT, delay=50)
            slow(1000)

        # Submit
        submit_btn = page.get_by_role("button", name="Submit").first
        if submit_btn.count() > 0:
            submit_btn.click()
            print("9. Input submitted!")
            slow(1000)
    except Exception as e:
        print(f"   Could not find input modal: {e}")

    # === 8. Watch live execution ===
    print("10. Watching live execution...")

    # Wait for Human Output modal (up to 5 minutes for Ollama)
    try:
        page.wait_for_selector("text=Workflow Output", timeout=300000)
        print("11. Human Output appeared!")
        slow(8000)  # Let user read the output

        # Close output modal
        close_btn = page.get_by_role("button", name="Close").first
        if close_btn.count() > 0:
            close_btn.click()
            slow(2000)
    except Exception:
        print("   Waiting for run to finish...")
        slow(10000)

    # === 9. Run Detail page ===
    print("12. Run Detail")
    slow(2000)

    # Get run_id from URL
    run_id = None
    if "/runs/" in page.url:
        run_id = page.url.split("/runs/")[-1].split("/")[0].split("?")[0]

    if run_id:
        # === 10. Debug ===
        print("13. Debug")
        page.goto(f"{BASE}/runs/{run_id}/debug", wait_until="networkidle")
        slow(1500)

        # Click through nodes
        node_btns = page.locator("button[class*='text-left']").all()
        for btn in node_btns[:5]:
            btn.click()
            slow(1500)
            page.mouse.wheel(0, 200)
            slow(500)
            page.mouse.wheel(0, -200)
            slow(300)

        # === 11. Trace ===
        print("14. Trace")
        page.goto(f"{BASE}/runs/{run_id}/trace", wait_until="networkidle")
        slow(2500)

        # === 12. Lineage ===
        print("15. Lineage")
        page.goto(f"{BASE}/runs/{run_id}/lineage", wait_until="networkidle")
        slow(2500)

        # === 13. Diagnose ===
        print("16. Diagnose")
        page.goto(f"{BASE}/runs/{run_id}/diagnose", wait_until="networkidle")
        slow(2000)

    # === End ===
    print("17. Back to Dashboard")
    page.goto(BASE, wait_until="networkidle")
    slow(2000)

    video_path = page.video.path()
    context.close()
    browser.close()

    print(f"\n✅ Demo recorded: {video_path}")
    print(f"Convert: ffmpeg -i '{video_path}' -c:v libx264 -preset fast -crf 22 /tmp/binex_demo/live_research_run.mp4")
