
import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to the game UI
        await page.goto("http://localhost:8888")

        # Give the page time to load
        await page.wait_for_selector(".char-marker")

        # --- Test Character Following and Details Panel ---

        # 1. Arrange: Find and click on a character marker to follow them.
        character_marker = page.locator(".char-marker").first
        await character_marker.click()

        # 2. Act: Wait for the character details panel to appear and find the "Personality" tab.
        character_panel = page.locator("#character-details-panel")
        await expect(character_panel).to_be_visible()

        personality_tab = character_panel.get_by_role("button", name="Personality")
        await expect(personality_tab).to_be_visible()
        await personality_tab.click()

        # 3. Assert: Check that the "Personality" tab content is visible.
        personality_content = character_panel.locator(".detail-tab-content.active")
        await expect(personality_content).to_contain_text("Archetype")

        # 4. Screenshot: Capture the state of the UI with the character followed and the personality tab open.
        await page.screenshot(path="jules-scratch/verification/character-details.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
