import { test, expect } from '@playwright/test';

test('Expert Signal Dismiss Test', async ({ page }) => {
  // Navigate to the app
  await page.goto('http://127.0.0.1:4000');

  // Wait for the UI to load
  await expect(page.locator('text=Kitty')).toBeVisible();

  // Find the 'Test Signal' in the UI
  // Note: Depending on the UI layout, it might be in a specific panel. We look for 'Test Signal' headline
  const signalHeadline = page.locator('text=Test Signal').first();
  await expect(signalHeadline).toBeVisible({ timeout: 10000 });

  // Find the corresponding Dismiss button for this signal.
  // Assuming the structure is a card/container with the headline and buttons.
  const signalCard = signalHeadline.locator('..').locator('..'); // go up to container (adjust if necessary)
  const dismissButton = signalCard.locator('button:has-text("Dismiss")');

  await expect(dismissButton).toBeVisible();

  // Click the Dismiss button
  await dismissButton.click();

  // Wait for the signal to disappear
  await expect(signalHeadline).not.toBeVisible({ timeout: 5000 });

  console.log('✅ Expert signal successfully dismissed and removed from UI!');
});
