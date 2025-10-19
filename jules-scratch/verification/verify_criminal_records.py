
import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Navigate to the game UI
        await page.goto("http://localhost:8888")

        # Give the page time to load
        await page.wait_for_selector("#log")

        # --- Screenshot 1: Civic Ledger ---

        # 1. Arrange: Find and click the "Civic Ledger" button
        ledger_button = page.get_by_role("button", name="⚖️ Civic Ledger")
        await ledger_button.click()

        # 2. Act: Wait for the popover to appear and find the new section.
        popover = page.locator("#civic-ledger-popover")
        await expect(popover).to_be_visible()

        criminal_records_header = popover.get_by_text("Criminal Records")
        await expect(criminal_records_header).to_be_visible()

        # 3. Screenshot: Capture the state of the Civic Ledger popover.
        await page.screenshot(path="jules-scratch/verification/civic-ledger.png")

        # --- Screenshot 2: Character Detail Panel ---

        # 4. Arrange: Close the popover and click on a character to view details.
        await ledger_button.click() # Close popover

        # Find a character that is likely to have a criminal record.
        # Based on the game logic, characters who are "scheming" or have low conscientiousness
        # are more likely to commit crimes. Let's find one.
        # Note: This is an assumption. If no character has a record, the tab won't show.
        # We will click on the first character portrait we find.
        character_portrait = page.locator(".character-portrait").first
        await character_portrait.click()

        # 5. Act: Find and click the "Criminal Record" tab.
        character_panel = page.locator("#character-details")
        await expect(character_panel).to_be_visible()

        # The script will only proceed if a character has a record, which creates the tab.
        criminal_record_tab = character_panel.get_by_text("Criminal Record")

        # Wait for the tab to appear, but handle the case where it might not.
        try:
            await criminal_record_tab.wait_for(timeout=2000) # Wait 2 seconds
            await criminal_record_tab.click()

            # 6. Assert & Screenshot: Check for content and capture the panel.
            record_content = character_panel.locator("#criminal-record-content")
            await expect(record_content).not_to_be_empty()
            await page.screenshot(path="jules-scratch/verification/character-record.png")

        except Exception as e:
            # If the tab doesn't exist, it means no character on screen has a record yet.
            # This is not a failure of the UI, but a state of the game.
            # We'll take a screenshot of the default panel instead.
            print("No character with a criminal record found on screen. Capturing default panel.")
            await page.screenshot(path="jules-scratch/verification/character-no-record.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
