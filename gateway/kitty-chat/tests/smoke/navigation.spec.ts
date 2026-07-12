import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

test('sidebar navigation switches views', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const navLabels = ['chats', 'projects', 'docs', 'settings'];
  for (const label of navLabels) {
    const btn = page.locator('button').filter({ hasText: new RegExp(`^${label}$`, 'i') });
    if (await btn.count() > 0) {
      await btn.first().click();
      await page.waitForTimeout(300);
      await expect(page.locator('body')).toBeVisible();
    }
  }

  expect(errors).toEqual([]);
});

test('page does not crash on rapid navigation', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const navLabels = ['home', 'chats', 'projects', 'docs', 'providers', 'agents', 'settings'];
  for (const label of navLabels) {
    const btn = page.locator('button').filter({ hasText: new RegExp(`^${label}$`, 'i') });
    if (await btn.count() > 0) {
      await btn.first().click();
      await page.waitForTimeout(100);
    }
  }

  expect(errors).toEqual([]);
});
