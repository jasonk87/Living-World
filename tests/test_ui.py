from playwright.sync_api import sync_playwright, expect
import re

def test_reputation_tier_display():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        try:
            page.goto("http://localhost:8080")

            # Wait for the initial game state to be loaded and rendered
            expect(page.locator("#hud-population-value")).not_to_be_empty(timeout=10000)

            # Click the button to open the characters panel
            page.locator('[data-panel="characters-panel"][aria-label="Open Citizens panel"]').click()

            # Wait for the panel to be visible
            panel = page.locator('#characters-panel')
            expect(panel).to_be_visible(timeout=5000)

            # Wait for at least one character card to be attached
            page.locator('.character-card').first.wait_for(state='attached', timeout=10000)

            # Find the first visible character card
            visible_card = None
            all_cards = page.locator('.character-card').all()
            for card in all_cards:
                if card.is_visible():
                    visible_card = card
                    break

            if not visible_card:
                page.screenshot(path="reputation_ui_no_visible_card.png")
                raise AssertionError("No visible character card found to test.")

            page.screenshot(path="reputation_ui.png")

            # Check for the reputation tier element within the visible card
            reputation_element = visible_card.locator('.reputation-tier')
            expect(reputation_element).to_be_visible()

            # Check that the text contains a valid tier.
            valid_tiers = re.compile(r"Venerated|Respected|Upstanding|Neutral|Unsavory|Shunned|Despised")
            expect(reputation_element).to_have_text(valid_tiers)

        except Exception as e:
            page.screenshot(path="reputation_ui_error.png")
            raise e

        finally:
            browser.close()
