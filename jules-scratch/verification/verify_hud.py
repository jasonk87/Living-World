
from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://localhost:8888")

        # Wait for the map to load
        page.wait_for_selector("#game-map")

        # Click on a character to select them
        page.click('.char-marker[data-name="Liam"]')

        # Wait for the HUD to appear
        page.wait_for_selector("#character-hud")

        # Take a screenshot
        page.screenshot(path="jules-scratch/verification/hud_verification.png")

        browser.close()

if __name__ == "__main__":
    run()
