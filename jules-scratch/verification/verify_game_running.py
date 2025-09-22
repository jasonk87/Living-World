from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the game's UI
            page.goto("http://localhost:8001", timeout=10000)

            # Check if the main title is there
            title = page.locator("h1")
            expect(title).to_have_text("Medieval Settlement Sim")

            print("Page title is correct. HTML is loading.")

            # Print the page content for debugging
            print("\n--- Page Content ---")
            print(page.content())
            print("--------------------\n")

            # Now, let's re-check the map container with a longer timeout
            map_container = page.locator("#map-container")
            expect(map_container).not_to_be_empty(timeout=20000)

            # Specifically wait for a character to appear on the map
            character_locator = page.locator(".char-marker").first
            expect(character_locator).to_be_visible(timeout=10000)

            # Take a screenshot of the initial game state
            page.screenshot(path="jules-scratch/verification/game_screenshot.png")

            print("Successfully took screenshot of the running game.")

        except Exception as e:
            print(f"An error occurred during verification: {e}")
            page.screenshot(path="jules-scratch/verification/error_screenshot.png")

        finally:
            browser.close()

if __name__ == "__main__":
    run_verification()
