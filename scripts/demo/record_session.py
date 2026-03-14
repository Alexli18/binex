"""Open a headed browser with video recording. Do whatever you want, then press Enter to stop."""
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8420"
VIDEO_DIR = "/tmp/binex_demo_session"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=VIDEO_DIR,
        record_video_size={"width": 1440, "height": 900},
    )
    page = context.new_page()
    page.goto(BASE, wait_until="networkidle")

    print(f"\n🎬 Recording started! Browser is open at {BASE}")
    print("Do whatever you want in the browser.")
    print("Press ENTER here when done to stop recording.\n")

    input()  # Wait for user

    video_path = page.video.path()
    context.close()
    browser.close()

    print(f"\n✅ Video saved: {video_path}")
    print(f"Convert: ffmpeg -i '{video_path}' -c:v libx264 -preset fast -crf 22 /tmp/binex_demo_session/demo.mp4")
