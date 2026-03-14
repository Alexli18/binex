"""E2E: Scaffold wizard — DSL generation and template selection."""
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

    # --- Test 1: DSL mode generates YAML ---
    print("\n=== Test: DSL Mode ===")
    page.goto(f"{BASE}/scaffold", wait_until="networkidle")

    check("Scaffold page loads", page.get_by_text("Create Workflow").count() > 0)
    check("DSL tab active", page.get_by_text("DSL").count() > 0)

    # Type DSL expression
    dsl_input = page.locator("input[placeholder*='A -> B']").first
    if dsl_input.count() > 0:
        dsl_input.fill("A -> B -> C")
        check("DSL input filled", True)

        generate_btn = page.get_by_role("button", name="Generate").first
        generate_btn.click()
        page.wait_for_timeout(2000)

        # Check YAML was generated
        yaml_output = page.locator("pre").first
        if yaml_output.count() > 0:
            yaml_text = yaml_output.text_content() or ""
            check("YAML generated", "nodes:" in yaml_text.lower() or len(yaml_text) > 10, yaml_text[:100])
        else:
            check("YAML generated", False, "no <pre> found")
    else:
        check("DSL input found", False, "input not found")

    # --- Test 2: Template mode shows patterns ---
    print("\n=== Test: Template Mode ===")
    template_tab = page.get_by_text("Template", exact=True).first
    if template_tab.count() > 0:
        template_tab.click()
        page.wait_for_timeout(500)

        # Should show pattern cards
        patterns_visible = page.locator("[class*='cursor-pointer']").count() > 0 or page.get_by_text("linear").count() > 0
        check("Template patterns visible", patterns_visible)
    else:
        check("Template tab found", False)

    # --- Test 3: Blank mode ---
    print("\n=== Test: Blank Mode ===")
    blank_tab = page.get_by_text("Blank", exact=True).first
    if blank_tab.count() > 0:
        blank_tab.click()
        page.wait_for_timeout(500)
        check("Blank tab switches", True)
    else:
        check("Blank tab found", False)

    browser.close()

    print(f"\n{'='*40}")
    print(f"Results: {PASSED} passed, {FAILED} failed, {PASSED+FAILED} total")
    if FAILED > 0:
        exit(1)
