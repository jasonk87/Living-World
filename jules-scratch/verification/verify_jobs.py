import asyncio
import subprocess
from playwright.async_api import async_playwright
import os

async def main():
    # Start the server
    server_process = subprocess.Popen(
        ["python3.12", "-m", "game.main"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )

    try:
        await asyncio.sleep(5)  # Wait for the server to start

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            try:
                await page.goto("http://localhost:8000/", timeout=60000)
                print("Successfully navigated to the page.")

                # Click on a character (e.g., the first one)
                await page.click("text=Alice", timeout=10000)
                print("Clicked on character 'Alice'.")

                # Click on the 'Career' tab
                await page.click("text=Career", timeout=10000)
                print("Clicked on 'Career' tab.")

                # Take a screenshot
                screenshot_path = "jules-scratch/verification/jobs_ui.png"
                await page.screenshot(path=screenshot_path)
                print(f"Screenshot saved to {screenshot_path}")

            except Exception as e:
                print(f"An error occurred during Playwright execution: {e}")

            finally:
                await browser.close()

    finally:
        # Shutdown the server
        os.killpg(os.getpgid(server_process.pid), 2)
        server_process.wait()
        print("Server process terminated.")

if __name__ == "__main__":
    asyncio.run(main())
