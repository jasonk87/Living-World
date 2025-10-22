from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:5000")

    # 1. Wait for the game to fully load.
    expect(page.locator("#map-meta")).not_to_contain_text("Awaiting telemetry…", timeout=10000)

    # 2. Open the economy popover.
    page.get_by_role("button", name="Toggle economy intel").click()

    # 3. Wait for the popover to be visible and stable.
    economy_popover = page.locator("#hud-popover-economy")
    expect(economy_popover).to_be_visible()
    page.wait_for_timeout(250) # Allow animations to settle.

    # 4. Use robust, user-facing locators to fill the form.
    page.get_by_label("Item:").select_option("Wooden_Chair")
    page.get_by_label("Quantity:").fill("3")
    page.get_by_role("button", name="Create Order").click()

    # 5. Wait for the success message and take a screenshot.
    success_message = page.locator("#work-order-status")
    expect(success_message).to_contain_text("Success! Order ID:")
    page.screenshot(path="jules-scratch/verification/work_order_verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
