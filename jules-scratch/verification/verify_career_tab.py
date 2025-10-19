from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto("http://localhost:5000/", timeout=60000)
            page.screenshot(path="jules-scratch/verification/career_tab.png")
            print("Screenshot saved to jules-scratch/verification/career_tab.png")
        except Exception as e:
            print(f"An error occurred during verification: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
