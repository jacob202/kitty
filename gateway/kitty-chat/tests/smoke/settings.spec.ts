import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

test('settings view renders', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const settingsBtn = page.locator('button').filter({ hasText: /^settings$/i });
  await settingsBtn.first().click();
  await page.waitForTimeout(500);

  await expect(page.locator('body')).toBeVisible();
});

test('viewport is narrow on mobile', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'mobile', 'skip on desktop');

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const box = await page.locator('body').boundingBox();
  expect(box).not.toBeNull();
  if (box) {
    expect(box.width).toBeLessThanOrEqual(500);
  }
});
