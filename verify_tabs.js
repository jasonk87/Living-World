const { test, expect } = require('@playwright/test');

test('Check for new tabs in character details panel', async ({ page }) => {
  await page.goto('http://localhost:5000');

  // Wait for the character list to be populated
  await page.waitForSelector('#character-list .character-card');

  // Click on the first character in the list
  await page.locator('#character-list .character-card').first().click();

  // Wait for the character details panel to be visible
  await page.waitForSelector('#character-details-panel.open');

  // Check for the new tabs
  await expect(page.locator('button.detail-tab-button:has-text("Social")')).toBeVisible();
  await expect(page.locator('button.detail-tab-button:has-text("Beliefs")')).toBeVisible();
  await expect(page.locator('button.detail-tab-button:has-text("Goals")')).toBeVisible();

  // Take a screenshot
  await page.screenshot({ path: 'new_tabs_screenshot.png' });
});
