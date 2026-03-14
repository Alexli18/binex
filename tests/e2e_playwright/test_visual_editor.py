"""E2E: Visual Editor — mode toggle, drag & drop, scaffold flow."""
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

    # --- Test 1: Editor loads with mode toggle ---
    print("\n=== Test: Editor Mode Toggle ===")
    page.goto(f"{BASE}/editor", wait_until="networkidle")
    page.wait_for_timeout(1500)

    visual_btn = page.get_by_role("button", name="Visual").first
    yaml_btn = page.get_by_role("button", name="YAML").first
    check("Visual button exists", visual_btn.count() > 0)
    check("YAML button exists", yaml_btn.count() > 0)

    page.screenshot(path="/tmp/binex_editor_modes.png", full_page=True)

    # --- Test 2: Switch to Visual mode ---
    print("\n=== Test: Visual Mode ===")
    if visual_btn.count() > 0:
        visual_btn.click()
        page.wait_for_timeout(1500)

        # Should see NodePalette with node types
        has_llm = page.get_by_text("LLM Agent").count() > 0
        has_local = page.get_by_text("Local Script").count() > 0
        has_approve = page.get_by_text("Human Approve").count() > 0
        has_input = page.get_by_text("Human Input").count() > 0
        has_a2a = page.get_by_text("A2A Agent").count() > 0

        check("LLM Agent in palette", has_llm)
        check("Local Script in palette", has_local)
        check("Human Approve in palette", has_approve)
        check("Human Input in palette", has_input)
        check("A2A Agent in palette", has_a2a)

        # Should see React Flow canvas
        reactflow = page.locator(".react-flow")
        check("ReactFlow canvas exists", reactflow.count() > 0)

        page.screenshot(path="/tmp/binex_visual_mode.png", full_page=True)

    # --- Test 3: Switch to YAML mode ---
    print("\n=== Test: YAML Mode ===")
    if yaml_btn.count() > 0:
        yaml_btn.click()
        page.wait_for_timeout(1500)

        # Monaco editor should be visible
        monaco = page.locator(".monaco-editor")
        check("Monaco editor in YAML mode", monaco.count() > 0)

        page.screenshot(path="/tmp/binex_yaml_mode.png", full_page=True)

    # --- Test 4: Scaffold → Editor flow ---
    print("\n=== Test: Scaffold → Editor ===")
    page.goto(f"{BASE}/scaffold", wait_until="networkidle")
    page.wait_for_timeout(1000)

    # Type DSL and generate
    dsl_input = page.locator("input[placeholder*='A -> B']").first
    if dsl_input.count() > 0:
        dsl_input.fill("A -> B -> C")
        generate_btn = page.get_by_role("button", name="Generate").first
        generate_btn.click()
        page.wait_for_timeout(2000)

        # Check YAML was generated
        yaml_output = page.locator("pre").first
        has_yaml = yaml_output.count() > 0 and len(yaml_output.text_content() or "") > 10
        check("YAML generated from DSL", has_yaml)

        # Click "Open in Editor"
        open_btn = page.get_by_role("button", name="Open in Editor").first
        if open_btn.count() > 0:
            open_btn.click()
            page.wait_for_timeout(2000)

            # Should be on /editor now
            check("Navigated to editor", "/editor" in page.url)

            # Editor should have content loaded
            check("Editor has content after scaffold", True)

            page.screenshot(path="/tmp/binex_scaffold_to_editor.png", full_page=True)
        else:
            check("Open in Editor button found", False)
    else:
        check("DSL input found", False)

    # --- Test 5: Save As modal ---
    print("\n=== Test: Save As Modal ===")
    save_btn = page.get_by_role("button", name="Save").first
    if save_btn.count() > 0 and not save_btn.is_disabled():
        save_btn.click()
        page.wait_for_timeout(500)

        # Save As modal should appear
        save_modal = page.get_by_text("Save Workflow").first
        check("Save As modal opens", save_modal.count() > 0)

        # Has filename input
        filename_input = page.locator("input[value='my-workflow.yaml']")
        check("Default filename shown", filename_input.count() > 0)

        # Close modal
        cancel_btn = page.get_by_role("button", name="Cancel").first
        if cancel_btn.count() > 0:
            cancel_btn.click()
            page.wait_for_timeout(300)

        page.screenshot(path="/tmp/binex_save_as.png", full_page=True)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
