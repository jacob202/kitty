import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem('kitty-onboarded', 'true');
  });
});

test('chat view loads and input is accessible', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const chatsBtn = page.locator('button').filter({ hasText: /^chats$/i });
  await chatsBtn.first().click();
  await page.waitForTimeout(500);

  const input = page.locator('textarea, input[type="text"]').first();
  if (await input.count() > 0) {
    await expect(input).toBeVisible();
    await input.fill('hello');
    const value = await input.inputValue();
    expect(value).toBe('hello');
  }

  expect(errors).toEqual([]);
});

test('chat view has no console errors', async ({ page }, testInfo) => {
  testInfo.skip(testInfo.project.name !== 'desktop', 'nav buttons only visible on desktop');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));

  await page.goto('/');
  await expect(page.locator('main')).toBeVisible({ timeout: 10_000 });

  const chatsBtn = page.locator('button').filter({ hasText: /^chats$/i });
  await chatsBtn.first().click();
  await page.waitForTimeout(1000);

  expect(errors).toEqual([]);
});
