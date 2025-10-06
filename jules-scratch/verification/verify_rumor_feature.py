import re
from playwright.sync_api import sync_playwright, Page, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    try:
        page.goto("http://localhost:5000")

        # Wait for the initial game state to load by looking for a specific element
        # that indicates the game is running, e.g., the pause button.
        expect(page.locator("#pause-button")).to_be_visible(timeout=15000)

        # Click the "World Intel" button to reveal the HUD panel
        world_intel_button = page.get_by_role("button", name="World Intel")
        world_intel_button.click()

        # The panel should now be visible
        hud_panel = page.locator("#hud-panel")
        expect(hud_panel).to_be_visible()

        # Wait for the rumor feed to contain text related to sickness or injury
        # This also serves as a functional test for the backend change.
        rumor_feed = hud_panel.locator("#rumor-feed-list")

        # Use a regex to find rumors about illness or injury
        # This is more robust than looking for a specific character name
        sick_or_injured_rumor = rumor_feed.get_by_text(re.compile(r"ill|injured", re.IGNORECASE))

        # Wait for the rumor to appear, with a generous timeout
        expect(sick_or_injured_rumor).to_be_visible(timeout=20000)

        # Take a screenshot of the entire HUD panel to show the rumor
        hud_panel.screenshot(path="jules-scratch/verification/verification.png")
        print("Screenshot taken of the World Intel panel with the new rumor.")

    except Exception as e:
        print(f"An error occurred during Playwright verification: {e}")
        # Take a screenshot anyway for debugging
        page.screenshot(path="jules-scratch/verification/error_screenshot.png")

    finally:
        browser.close()

with sync_playwright() as playwright:
    run(playwright)