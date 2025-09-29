from playwright.sync_api import sync_playwright, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("http://localhost:5000", timeout=10000)

            # Wait for the map to be ready
            page.wait_for_selector("#game-map", timeout=5000)

            # Wait for a character marker to appear and click it
            character_marker = page.locator(".char-marker").first
            expect(character_marker).to_be_visible(timeout=5000)
            character_marker.click()

            # Wait for the details panel to update with the character's name
            # This confirms the click was processed
            details_panel = page.locator("#entity-details")
            expect(details_panel).to_contain_text("Money", timeout=2000)

            page.screenshot(path="jules-scratch/verification/verification.png")
            print("Screenshot of character details taken successfully.")

        except Exception as e:
            print(f"An error occurred during Playwright verification: {e}")
            page.screenshot(path="jules-scratch/verification/error_screenshot.png")
            print("Error screenshot taken.")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
