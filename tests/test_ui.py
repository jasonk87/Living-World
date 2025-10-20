from playwright.sync_api import sync_playwright

def test_reputation_tier_display():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        try:
            page.goto("http://localhost:5000")
            page.wait_for_timeout(5000) # Wait for UI to render

            screenshot_path = "reputation_ui.png"
            page.screenshot(path=screenshot_path)
            print(f"Screenshot saved to {screenshot_path}")

        finally:
            browser.close()
