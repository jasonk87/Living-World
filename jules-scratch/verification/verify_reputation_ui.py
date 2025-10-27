from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:8080")

    # Click the specific button to open the characters panel
    page.locator("button.overlay-toggle[data-panel='characters-panel']").click()

    # Use the :visible pseudo-selector to target only the rendered character cards
    visible_card = page.locator(".character-card:visible").first

    # Wait for the first visible card to be ready
    visible_card.wait_for(state="visible")

    # Hover over the visible card
    visible_card.hover()

    # Wait for the tooltip to appear after hovering
    page.wait_for_selector(".character-details-tooltip", state="visible")

    # Take a screenshot of just the card and its tooltip
    visible_card.screenshot(path="jules-scratch/verification/reputation_ui.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
